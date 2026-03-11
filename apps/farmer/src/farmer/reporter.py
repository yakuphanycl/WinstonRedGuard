from __future__ import annotations

from .seed_bank import load_seeds
from .storage import load_rows


def _count_by(rows: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field, "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))


def report_summary() -> dict:
    seeds = load_seeds()
    growth_jobs = load_rows("growth_jobs")
    harvests = load_rows("harvests")
    warehouse = load_rows("warehouse")
    decisions = load_rows("decisions")

    return {
        "total_seeds": len(seeds),
        "seed_status_counts": _count_by(seeds, "status"),
        "growth_jobs_count": len(growth_jobs),
        "harvest_count": len(harvests),
        "warehouse_bucket_counts": _count_by(warehouse, "bucket"),
        "decision_counts": _count_by(decisions, "decision"),
    }
