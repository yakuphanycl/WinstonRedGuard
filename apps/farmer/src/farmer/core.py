from __future__ import annotations

from .care_engine import care_run as _care_run
from .care_engine import care_show as _care_show
from .event_log import list_events, recent_events
from .growth_engine import grow_run as _grow_run
from .growth_engine import grow_show as _grow_show
from .growth_engine import start_growth
from .harvest_manager import harvest_check as _harvest_check
from .harvest_manager import harvest_list as _harvest_list
from .harvest_manager import harvest_run as _harvest_run
from .reporter import report_summary as _report_summary
from .scoring import score_seed
from .seed_bank import LIFECYCLE_STATES, add_seed, find_seed, load_seeds, require_seed, set_score_result, set_status
from .selector import list_decisions as _list_decisions
from .selector import latest_decision
from .selector import SELECTABLE_STATUSES
from .selector import select_seed as _select_seed
from .storage import load_rows
from .warehouse import VALID_BUCKETS, store_harvested, warehouse_list as _warehouse_list
from .warehouse import warehouse_move as _warehouse_move
from .warehouse import warehouse_show as _warehouse_show

RECENT_EVENTS_LIMIT = 5


def seed_add(
    name: str,
    title: str | None,
    category: str,
    problem: str,
    target_user: str,
    internal_value: int,
    external_value: int,
    complexity: int,
) -> dict:
    return add_seed(
        name=name,
        title=title,
        category=category,
        problem=problem,
        target_user=target_user,
        internal_value=internal_value,
        external_value=external_value,
        complexity=complexity,
    )


def seed_list() -> list[dict]:
    return sorted(load_seeds(), key=lambda row: str(row.get("name", "")))


def seed_show(name: str) -> dict:
    seed = require_seed(name)
    decision = latest_decision(name)
    selection = None
    if decision is not None:
        selection = {
            "selected": bool(decision.get("selected")),
            "reason_codes": [str(code) for code in list(decision.get("reason_codes", []))],
        }
    return {
        "seed": seed,
        "selection": selection,
        "recent_events": recent_events(name, limit=RECENT_EVENTS_LIMIT),
    }


def seed_score(name: str) -> dict:
    result = score_seed(name)
    set_score_result(name, result)
    return result


def seed_queue(name: str) -> dict:
    seed = require_seed(name)
    allowed = {"scored", "seed", "hold"}
    if seed.get("status") not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"cannot queue seed from status: {seed.get('status')} "
            f"(allowed: {allowed_text})"
        )
    return set_status(name, "queued")


def grow_start(name: str) -> dict:
    return start_growth(name)


def grow_run() -> list[dict]:
    return _grow_run()


def grow_show(name: str) -> dict:
    return _grow_show(name)


def care_run() -> list[dict]:
    return _care_run()


def care_show(name: str) -> dict:
    return _care_show(name)


def harvest_check(name: str) -> dict:
    return _harvest_check(name)


def harvest_run() -> list[dict]:
    results = _harvest_run()
    for row in results:
        if row.get("harvestable") is True:
            store_harvested(str(row.get("seed_name")))
    return results


def harvest_list() -> list[dict]:
    return _harvest_list()


def warehouse_list() -> list[dict]:
    return _warehouse_list()


def warehouse_show(name: str) -> dict:
    return _warehouse_show(name)


def warehouse_move(name: str, bucket: str) -> dict:
    return _warehouse_move(name, bucket)


def select(name: str) -> dict:
    return _select_seed(name)


def decisions_list() -> list[dict]:
    return _list_decisions()


def report_summary() -> dict:
    return _report_summary()


def events(seed_name: str | None = None) -> dict:
    if seed_name is not None:
        _ = require_seed(seed_name)
    rows = list_events(seed_name=seed_name)
    return {"total": len(rows), "events": rows}


def doctor_report() -> dict:
    seeds = load_seeds()
    decisions = load_rows("decisions")
    wh_rows = load_rows("warehouse")
    event_rows = list_events()
    seed_names = {str(row.get("name")) for row in seeds if str(row.get("name", "")).strip()}

    findings: list[dict] = []

    def add_finding(severity: str, code: str, seed_name: str | None, message: str) -> None:
        findings.append(
            {
                "severity": severity,
                "code": code,
                "seed_name": seed_name,
                "message": message,
            }
        )

    for row in seeds:
        name = str(row.get("name", ""))
        status = str(row.get("status", ""))
        if status not in LIFECYCLE_STATES:
            add_finding("ERROR", "invalid_seed_status", name, f"seed has unknown status: {status}")

    for row in decisions:
        name = str(row.get("name", ""))
        if not name or name not in seed_names:
            add_finding("ERROR", "orphan_selector_record", name or None, "selector decision exists for missing seed")
            continue
        if bool(row.get("selected")) and str(require_seed(name).get("status", "")) not in SELECTABLE_STATUSES:
            add_finding(
                "WARNING",
                "selection_state_contradiction",
                name,
                "selected decision conflicts with current seed lifecycle state",
            )

    for row in event_rows:
        seed_name = str(row.get("seed_name", ""))
        if not seed_name or seed_name not in seed_names:
            add_finding("WARNING", "orphan_event_record", seed_name or None, "event exists for missing seed")

    for row in wh_rows:
        seed_name = str(row.get("name", ""))
        bucket = str(row.get("bucket", ""))
        if not seed_name or seed_name not in seed_names:
            add_finding("ERROR", "invalid_bucket_reference", seed_name or None, "warehouse entry exists for missing seed")
            continue
        if bucket not in VALID_BUCKETS:
            add_finding("ERROR", "invalid_bucket_reference", seed_name, f"warehouse bucket is invalid: {bucket}")

    severity_order = {"ERROR": 0, "WARNING": 1}
    findings = sorted(
        findings,
        key=lambda row: (
            severity_order.get(str(row.get("severity", "")), 99),
            str(row.get("code", "")),
            "" if row.get("seed_name") is None else str(row.get("seed_name", "")),
            str(row.get("message", "")),
        ),
    )

    errors = sum(1 for row in findings if row.get("severity") == "ERROR")
    warnings = sum(1 for row in findings if row.get("severity") == "WARNING")
    overall = "ERROR" if errors > 0 else ("WARNING" if warnings > 0 else "OK")
    return {
        "summary": {
            "total": len(findings),
            "errors": errors,
            "warnings": warnings,
            "overall": overall,
        },
        "findings": findings,
    }


def bootstrap_data_files() -> None:
    for kind in ("seeds", "growth_jobs", "harvests", "warehouse", "decisions", "activity_log"):
        _ = load_rows(kind)
