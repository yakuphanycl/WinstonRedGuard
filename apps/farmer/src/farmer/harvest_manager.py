from __future__ import annotations

from .event_log import append_event
from .seed_bank import require_seed, set_status
from .storage import append_row, load_rows, now_iso_utc

HARVEST_SCORE_THRESHOLD = 24


def harvest_check(seed_name: str) -> dict:
    seed = require_seed(seed_name)
    status = str(seed.get("status", ""))
    score = int(seed.get("score") or 0)

    issues: list[str] = []
    if status not in {"maturing", "harvestable"}:
        issues.append("status must be maturing or harvestable")
    if score < HARVEST_SCORE_THRESHOLD:
        issues.append(f"score below threshold {HARVEST_SCORE_THRESHOLD}")
    if status in {"retired", "composted"}:
        issues.append("retired/composted cannot be harvested")
    if not str(seed.get("problem", "")).strip() or not str(seed.get("target_user", "")).strip():
        issues.append("required fields are incomplete")

    return {
        "seed_name": seed_name,
        "harvestable": len(issues) == 0,
        "issues": issues,
        "score": score,
        "status": status,
    }


def _record_harvest(seed_name: str, score: int) -> dict:
    ts = now_iso_utc()
    return append_row(
        "harvests",
        {
            "seed_name": seed_name,
            "score": score,
            "event": "harvested",
            "created_at": ts,
            "updated_at": ts,
        },
        sort_key="seed_name",
    )


def harvest_run() -> list[dict]:
    outcomes: list[dict] = []
    seeds = load_rows("seeds")
    for seed in sorted(seeds, key=lambda r: str(r.get("name", ""))):
        name = str(seed.get("name", ""))
        if not name:
            continue
        check = harvest_check(name)
        if not check["harvestable"]:
            outcomes.append(check)
            continue

        set_status(name, "harvested")
        _record_harvest(name, int(seed.get("score") or 0))
        append_event("harvested", name, {"status": "harvested"})
        outcomes.append({"seed_name": name, "harvestable": True, "action": "harvested"})

    return outcomes


def harvest_list() -> list[dict]:
    return load_rows("harvests")
