from __future__ import annotations

from .seed_bank import load_seeds, set_status
from .storage import find_row, update_row


def care_run() -> list[dict]:
    seeds = [row for row in load_seeds() if row.get("status") in {"growing", "maturing"}]
    output: list[dict] = []

    for seed in sorted(seeds, key=lambda r: str(r.get("name", ""))):
        notes: list[str] = []
        if not str(seed.get("problem", "")).strip() or not str(seed.get("target_user", "")).strip():
            notes.append("missing clarity")
        if int(seed.get("complexity", 0)) >= 7:
            notes.append("high complexity risk")
        if int(seed.get("external_value", 0)) <= 3:
            notes.append("weak external value")
        if int(seed.get("internal_value", 0)) >= 7:
            notes.append("internal fit is strong")

        next_status = str(seed.get("status"))
        if next_status == "growing" and "missing clarity" not in notes and "high complexity risk" not in notes:
            next_status = "maturing"
            set_status(seed["name"], "maturing")

        job = find_row("growth_jobs", "seed_name", seed["name"])
        if job is not None:
            update_row(
                "growth_jobs",
                "seed_name",
                seed["name"],
                {
                    "last_action": "care-run",
                    "care_notes": notes,
                    "readiness_hints": [f"care status {next_status}"],
                    "current_growth_stage": next_status,
                },
                sort_key="seed_name",
            )

        output.append({"seed_name": seed["name"], "status": next_status, "notes": notes})

    return output


def care_show(seed_name: str) -> dict:
    job = find_row("growth_jobs", "seed_name", seed_name)
    if job is None:
        raise ValueError(f"growth job not found: {seed_name}")
    return {
        "seed_name": seed_name,
        "status": job.get("current_growth_stage"),
        "care_notes": list(job.get("care_notes", [])),
        "readiness_hints": list(job.get("readiness_hints", [])),
    }
