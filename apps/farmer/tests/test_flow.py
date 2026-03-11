from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from farmer import cli
from farmer.seed_bank import set_status
from farmer.storage import load_rows, now_iso_utc, save_rows


@pytest.fixture
def isolated_data_dir() -> Path:
    base_tmp = Path(__file__).resolve().parent / ".tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    tmpdir = base_tmp / f"farmer_v2_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=False)

    old = os.environ.get("FARMER_DATA_DIR")
    old_legacy = os.environ.get("FARMER_DATA_PATH")
    os.environ["FARMER_DATA_DIR"] = str(tmpdir)
    os.environ.pop("FARMER_DATA_PATH", None)
    try:
        yield tmpdir
    finally:
        if old is None:
            os.environ.pop("FARMER_DATA_DIR", None)
        else:
            os.environ["FARMER_DATA_DIR"] = old
        if old_legacy is None:
            os.environ.pop("FARMER_DATA_PATH", None)
        else:
            os.environ["FARMER_DATA_PATH"] = old_legacy
        shutil.rmtree(tmpdir, ignore_errors=True)


def _seed_add_args(name: str, *, internal: int = 8, external: int = 7, complexity: int = 3) -> list[str]:
    return [
        "seed",
        "add",
        "--name",
        name,
        "--title",
        f"{name} title",
        "--category",
        "automation",
        "--problem",
        "manual repetitive work",
        "--target-user",
        "ops team",
        "--internal-value",
        str(internal),
        "--external-value",
        str(external),
        "--complexity",
        str(complexity),
    ]


def _event_types() -> list[str]:
    return [row["event_type"] for row in load_rows("activity_log")]


def test_seed_add_success(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("idea_one")) == 0
    rows = load_rows("seeds")
    assert len(rows) == 1
    assert rows[0]["name"] == "idea_one"
    assert rows[0]["status"] == "seed"
    assert "seed_added" in _event_types()


def test_duplicate_seed_rejected(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("dup")) == 0
    assert cli.main(_seed_add_args("dup")) == 1


def test_seed_score_updates_status_and_score_data(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("score_me")) == 0
    assert cli.main(["seed", "score", "score_me"]) == 0

    row = load_rows("seeds")[0]
    assert row["status"] == "scored"
    assert isinstance(row["score"], int)
    assert isinstance(row["score_breakdown"], dict)
    assert row["decision_hint"] in {"grow", "hold", "retire"}
    assert "score_result_set" in _event_types()


def test_seed_queue_and_grow_start_work(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("grow_path")) == 0
    assert cli.main(["seed", "score", "grow_path"]) == 0
    assert cli.main(["seed", "queue", "grow_path"]) == 0
    assert cli.main(["grow", "start", "grow_path"]) == 0

    seed = load_rows("seeds")[0]
    jobs = load_rows("growth_jobs")
    assert seed["status"] == "sprout"
    assert jobs[0]["seed_name"] == "grow_path"
    assert "growth_started" in _event_types()


def test_grow_run_advances_lifecycle_deterministically(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("advance")) == 0
    assert cli.main(["seed", "score", "advance"]) == 0
    assert cli.main(["grow", "start", "advance"]) == 0

    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0

    seed = load_rows("seeds")[0]
    assert seed["status"] in {"maturing", "harvestable"}


def test_care_run_produces_notes(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("careful", complexity=8, external=2)) == 0
    assert cli.main(["seed", "score", "careful"]) == 0
    assert cli.main(["grow", "start", "careful"]) == 0
    assert cli.main(["grow", "run"]) == 0

    assert cli.main(["care", "run"]) == 0
    assert cli.main(["care", "show", "careful"]) == 0

    job = load_rows("growth_jobs")[0]
    assert isinstance(job.get("care_notes"), list)


def test_harvest_check_and_run_behavior(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("harvest_me")) == 0
    assert cli.main(["seed", "score", "harvest_me"]) == 0
    assert cli.main(["grow", "start", "harvest_me"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0

    assert cli.main(["harvest", "check", "harvest_me"]) == 0
    assert cli.main(["harvest", "run"]) == 0

    seed = load_rows("seeds")[0]
    harvests = load_rows("harvests")
    assert seed["status"] in {"harvested", "stored"}
    assert len(harvests) >= 1
    assert "harvested" in _event_types()


def test_warehouse_move_valid_and_invalid(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("ware")) == 0
    assert cli.main(["seed", "score", "ware"]) == 0
    assert cli.main(["grow", "start", "ware"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["harvest", "run"]) == 0

    assert cli.main(["warehouse", "move", "ware", "--to", "external_candidates"]) == 0
    assert cli.main(["warehouse", "move", "ware", "--to", "invalid_bucket"]) == 1
    assert "warehouse_moved" in _event_types()


def test_select_persists_expected_decision(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("pick", internal=9, external=8, complexity=2)) == 0
    assert cli.main(["seed", "score", "pick"]) == 0
    assert cli.main(["grow", "start", "pick"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["harvest", "run"]) == 0
    assert cli.main(["warehouse", "move", "pick", "--to", "external_candidates"]) == 0

    assert cli.main(["select", "pick"]) == 0
    decisions = load_rows("decisions")
    assert len(decisions) == 1
    assert decisions[0]["decision"] in {
        "hire_internal",
        "promote_external",
        "send_to_refinery",
        "hold",
        "retire",
    }
    assert isinstance(decisions[0].get("selected"), bool)
    assert isinstance(decisions[0].get("reason_codes"), list)
    assert "seed_selected" in _event_types()

    assert cli.main(["select", "pick"]) == 0
    decisions = load_rows("decisions")
    assert len(decisions) == 1
    seed_selected_events = [row for row in load_rows("activity_log") if row.get("event_type") == "seed_selected" and row.get("seed_name") == "pick"]
    assert len(seed_selected_events) == 1


def test_events_cli_all_seed_filter_and_json(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("e1")) == 0
    assert cli.main(_seed_add_args("e2")) == 0
    assert cli.main(["seed", "score", "e1"]) == 0

    _ = capsys.readouterr()
    assert cli.main(["events"]) == 0
    human = capsys.readouterr().out
    assert "events:" in human

    assert cli.main(["events", "--seed", "e1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {"events", "total"}
    assert all(row["seed_name"] == "e1" for row in payload["events"])

    assert cli.main(["events", "--seed", "missing_seed"]) == 1
    out = capsys.readouterr().out
    assert "error: seed not found: missing_seed" in out


def test_show_json_shape_without_selection(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("intel_a")) == 0
    _ = capsys.readouterr()
    assert cli.main(["seed", "show", "intel_a", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {"recent_events", "seed", "selection"}
    assert payload["seed"]["name"] == "intel_a"
    assert payload["selection"] is None
    assert isinstance(payload["recent_events"], list)
    assert len(payload["recent_events"]) >= 1


def test_show_json_includes_latest_selector_decision(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("intel_b", internal=9, external=8, complexity=2)) == 0
    assert cli.main(["seed", "score", "intel_b"]) == 0
    assert cli.main(["grow", "start", "intel_b"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["harvest", "run"]) == 0
    assert cli.main(["warehouse", "move", "intel_b", "--to", "external_candidates"]) == 0
    assert cli.main(["select", "intel_b"]) == 0

    _ = capsys.readouterr()
    assert cli.main(["show", "intel_b", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["selection"] is not None
    assert isinstance(payload["selection"]["selected"], bool)
    assert isinstance(payload["selection"]["reason_codes"], list)


def test_show_recent_events_bounded_and_deterministic(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("intel_c")) == 0
    assert cli.main(["seed", "score", "intel_c"]) == 0
    assert cli.main(["seed", "queue", "intel_c"]) == 0
    assert cli.main(["grow", "start", "intel_c"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["harvest", "run"]) == 0
    assert cli.main(["warehouse", "move", "intel_c", "--to", "refine_queue"]) == 0
    assert cli.main(["select", "intel_c"]) == 0

    _ = capsys.readouterr()
    assert cli.main(["seed", "show", "intel_c", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    recent = payload["recent_events"]
    assert len(recent) == 5
    all_for_seed = [row for row in load_rows("activity_log") if row.get("seed_name") == "intel_c"]
    expected = list(reversed(all_for_seed[-5:]))
    assert recent == expected


def test_show_json_handles_seed_with_no_events(isolated_data_dir: Path, capsys) -> None:
    ts = now_iso_utc()
    save_rows(
        "seeds",
        [
            {
                "name": "intel_no_events",
                "title": "",
                "category": "automation",
                "problem": "x",
                "target_user": "y",
                "internal_value": 1,
                "external_value": 1,
                "complexity": 1,
                "status": "seed",
                "score": None,
                "score_breakdown": None,
                "score_reasons": [],
                "decision_hint": None,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
        sort_key="name",
    )

    _ = capsys.readouterr()
    assert cli.main(["show", "intel_no_events", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["selection"] is None
    assert payload["recent_events"] == []


def test_report_summary_works(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("summary_seed")) == 0
    _ = capsys.readouterr()
    assert cli.main(["report", "summary"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "total_seeds" in payload
    assert "seed_status_counts" in payload
    assert "growth_jobs_count" in payload
    assert "harvest_count" in payload
    assert "warehouse_bucket_counts" in payload
    assert "decision_counts" in payload


def test_doctor_clean_data_reports_ok(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("doctor_clean")) == 0
    _ = capsys.readouterr()
    assert cli.main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["overall"] == "OK"
    assert payload["summary"]["errors"] == 0
    assert payload["summary"]["warnings"] == 0
    assert payload["findings"] == []


def test_doctor_orphan_selector_record_is_error(isolated_data_dir: Path, capsys) -> None:
    ts = now_iso_utc()
    save_rows(
        "decisions",
        [
            {
                "name": "ghost_seed",
                "decision": "hold",
                "reason": "x",
                "selected": False,
                "reason_codes": [],
                "score": 0,
                "status": "seed",
                "bucket": None,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
        sort_key="name",
    )
    _ = capsys.readouterr()
    code = cli.main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["summary"]["errors"] == 1
    assert payload["findings"][0]["code"] == "orphan_selector_record"
    assert payload["findings"][0]["severity"] == "ERROR"


def test_doctor_orphan_event_record_is_warning(isolated_data_dir: Path, capsys) -> None:
    save_rows(
        "activity_log",
        [
            {
                "event_type": "seed_added",
                "seed_name": "ghost_event_seed",
                "timestamp": now_iso_utc(),
                "payload": {"status": "seed"},
            }
        ],
        sort_key="timestamp",
    )
    _ = capsys.readouterr()
    assert cli.main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["overall"] == "WARNING"
    assert payload["summary"]["warnings"] == 1
    assert payload["findings"][0]["code"] == "orphan_event_record"
    assert payload["findings"][0]["severity"] == "WARNING"


def test_doctor_invalid_seed_status_is_error(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("bad_status")) == 0
    rows = load_rows("seeds")
    rows[0]["status"] = "unknown_state"
    save_rows("seeds", rows, sort_key="name")

    _ = capsys.readouterr()
    code = cli.main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["summary"]["errors"] == 1
    assert payload["findings"][0]["code"] == "invalid_seed_status"


def test_doctor_warehouse_inconsistency_detected(isolated_data_dir: Path, capsys) -> None:
    ts = now_iso_utc()
    save_rows(
        "warehouse",
        [
            {
                "name": "ghost_in_warehouse",
                "bucket": "invalid_bucket",
                "created_at": ts,
                "updated_at": ts,
            }
        ],
        sort_key="name",
    )
    _ = capsys.readouterr()
    code = cli.main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["summary"]["errors"] >= 1
    assert any(item["code"] == "invalid_bucket_reference" for item in payload["findings"])


def test_doctor_selection_state_contradiction_detected(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("contradiction_seed")) == 0
    ts = now_iso_utc()
    save_rows(
        "decisions",
        [
            {
                "name": "contradiction_seed",
                "decision": "hire_internal",
                "reason": "x",
                "selected": True,
                "reason_codes": ["status_allowed"],
                "score": 30,
                "status": "stored",
                "bucket": "internal_stock",
                "created_at": ts,
                "updated_at": ts,
            }
        ],
        sort_key="name",
    )
    _ = capsys.readouterr()
    assert cli.main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["overall"] == "WARNING"
    assert any(item["code"] == "selection_state_contradiction" for item in payload["findings"])


def test_doctor_json_deterministic_ordering(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("ordering_seed")) == 0
    seeds = load_rows("seeds")
    seeds[0]["status"] = "bad_status"
    save_rows("seeds", seeds, sort_key="name")

    ts = now_iso_utc()
    save_rows(
        "decisions",
        [
            {
                "name": "ghost_ordering",
                "decision": "hold",
                "reason": "x",
                "selected": False,
                "reason_codes": [],
                "score": 0,
                "status": "seed",
                "bucket": None,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
        sort_key="name",
    )
    save_rows(
        "activity_log",
        [
            {
                "event_type": "seed_added",
                "seed_name": "ghost_ordering",
                "timestamp": ts,
                "payload": {"status": "seed"},
            }
        ],
        sort_key="timestamp",
    )

    _ = capsys.readouterr()
    code = cli.main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    codes = [item["code"] for item in payload["findings"]]
    assert codes == ["invalid_seed_status", "orphan_selector_record", "orphan_event_record"]


def test_doctor_is_read_only(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("readonly_seed")) == 0
    files = [
        "seeds.json",
        "growth_jobs.json",
        "harvests.json",
        "warehouse.json",
        "decisions.json",
        "activity_log.json",
    ]
    before = {}
    for name in files:
        path = isolated_data_dir / name
        before[name] = path.read_text(encoding="utf8")

    _ = capsys.readouterr()
    assert cli.main(["doctor"]) == 0
    _ = capsys.readouterr()

    after = {}
    for name in files:
        path = isolated_data_dir / name
        after[name] = path.read_text(encoding="utf8")
    assert after == before


def test_invalid_transition_grow_start_from_retired(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("retired_seed")) == 0
    set_status("retired_seed", "retired")

    _ = capsys.readouterr()
    code = cli.main(["grow", "start", "retired_seed"])
    out = capsys.readouterr().out
    assert code == 1
    assert "cannot start growth from status" in out


def test_invalid_transition_seed_queue_from_stored(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("stored_seed")) == 0
    assert cli.main(["seed", "score", "stored_seed"]) == 0
    set_status("stored_seed", "queued")
    set_status("stored_seed", "sprout")
    set_status("stored_seed", "growing")
    set_status("stored_seed", "maturing")
    set_status("stored_seed", "harvestable")
    set_status("stored_seed", "harvested")
    set_status("stored_seed", "stored")

    _ = capsys.readouterr()
    code = cli.main(["seed", "queue", "stored_seed"])
    out = capsys.readouterr().out
    assert code == 1
    assert "cannot queue seed from status" in out


def test_not_found_errors_are_user_friendly(isolated_data_dir: Path, capsys) -> None:
    code_seed = cli.main(["seed", "show", "missing_seed"])
    out_seed = capsys.readouterr().out
    assert code_seed == 1
    assert "error: seed not found: missing_seed" in out_seed

    code_growth = cli.main(["grow", "show", "missing_seed"])
    out_growth = capsys.readouterr().out
    assert code_growth == 1
    assert "error: growth job not found: missing_seed" in out_growth


def test_select_on_invalid_lifecycle_state_fails(isolated_data_dir: Path, capsys) -> None:
    assert cli.main(_seed_add_args("raw_seed")) == 0
    _ = capsys.readouterr()
    code = cli.main(["select", "raw_seed"])
    out = capsys.readouterr().out
    assert code == 1
    assert "error: invalid lifecycle state for select:" in out


def test_repeated_harvest_run_is_idempotent(isolated_data_dir: Path) -> None:
    assert cli.main(_seed_add_args("idempotent")) == 0
    assert cli.main(["seed", "score", "idempotent"]) == 0
    assert cli.main(["grow", "start", "idempotent"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["grow", "run"]) == 0
    assert cli.main(["harvest", "run"]) == 0
    first_count = len(load_rows("harvests"))
    first_event_count = len([row for row in load_rows("activity_log") if row.get("event_type") == "harvested" and row.get("seed_name") == "idempotent"])

    assert cli.main(["harvest", "run"]) == 0
    second_count = len(load_rows("harvests"))
    second_event_count = len([row for row in load_rows("activity_log") if row.get("event_type") == "harvested" and row.get("seed_name") == "idempotent"])
    assert second_count == first_count
    assert second_event_count == first_event_count
