from __future__ import annotations

from .core import get_required_record, upsert_record

BUNDLE_RULES = {
    "app_registry": ["app_evaluator", "repo_analyzer"],
    "app_evaluator": ["app_registry", "repo_analyzer"],
    "farmer": ["refinery"],
    "refinery": ["farmer"],
}


def suggest_bundle(app_name: str) -> dict:
    row = get_required_record(app_name)
    candidates = list(BUNDLE_RULES.get(app_name, []))
    next_status = row.get("status", "reviewing")
    if candidates:
        next_status = "bundled"

    return upsert_record(
        app_name,
        {
            "bundle_candidates": candidates,
            "status": next_status,
            "last_action": "bundle-suggest",
        },
    )
