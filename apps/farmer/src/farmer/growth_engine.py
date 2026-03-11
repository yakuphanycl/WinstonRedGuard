from __future__ import annotations

from .event_log import append_event
from .seed_bank import require_seed, set_status
from .storage import find_row, load_rows, now_iso_utc, save_rows, update_row


def _ensure_job(seed_name: str) -> dict:
    job = find_row("growth_jobs", "seed_name", seed_name)
    if job is not None:
        return job
    ts = now_iso_utc()
    row = {
        "seed_name": seed_name,
        "current_growth_stage": "sprout",
        "last_action": "grow-start",
        "readiness_hints": [],
        "care_notes": [],
        "created_at": ts,
        "updated_at": ts,
    }
    jobs = load_rows("growth_jobs")
    jobs.append(row)
    save_rows("growth_jobs", jobs, sort_key="seed_name")
    return row


def start_growth(seed_name: str) -> dict:
    seed = require_seed(seed_name)
    from_status = str(seed.get("status", ""))
    allowed = {"scored", "queued", "seed"}
    if from_status not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"cannot start growth from status: {from_status} "
            f"(allowed: {allowed_text})"
        )

    if from_status in {"seed", "scored"}:
        set_status(seed_name, "queued")

    set_status(seed_name, "sprout")
    _ = _ensure_job(seed_name)
    row = update_row(
        "growth_jobs",
        "seed_name",
        seed_name,
        {
            "current_growth_stage": "sprout",
            "last_action": "grow-start",
        },
        sort_key="seed_name",
    )
    append_event("growth_started", seed_name, {"from_status": from_status, "to_status": "sprout"})
    return row


def grow_show(seed_name: str) -> dict:
    job = find_row("growth_jobs", "seed_name", seed_name)
    if job is None:
        raise ValueError(f"growth job not found: {seed_name}")
    return job


def grow_run() -> list[dict]:
    jobs = load_rows("growth_jobs")
    if not jobs:
        return []

    transitions = {"sprout": "growing", "growing": "maturing", "maturing": "harvestable"}
    updated: list[dict] = []

    for job in sorted(jobs, key=lambda r: str(r.get("seed_name", ""))):
        seed_name = str(job.get("seed_name", ""))
        if not seed_name:
            continue
        current = str(job.get("current_growth_stage", "sprout"))
        seed_status = str(require_seed(seed_name).get("status", ""))
        if seed_status in {"retired", "composted", "stored"}:
            merged = update_row(
                "growth_jobs",
                "seed_name",
                seed_name,
                {
                    "last_action": "grow-run-skipped",
                    "readiness_hints": [f"skipped due to seed status {seed_status}"],
                },
                sort_key="seed_name",
            )
            updated.append(merged)
            continue
        next_stage = transitions.get(current, current)

        if next_stage == "harvestable":
            set_status(seed_name, "harvestable")
        elif next_stage == "maturing":
            set_status(seed_name, "maturing")
        elif next_stage == "growing":
            set_status(seed_name, "growing")
        else:
            set_status(seed_name, current)

        merged = update_row(
            "growth_jobs",
            "seed_name",
            seed_name,
            {
                "current_growth_stage": next_stage,
                "last_action": "grow-run",
                "readiness_hints": [f"stage moved to {next_stage}"],
            },
            sort_key="seed_name",
        )
        updated.append(merged)

    return updated
