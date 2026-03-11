from __future__ import annotations

from .seed_bank import require_seed

STRATEGIC_FIT_BY_CATEGORY = {
    "infra": 3,
    "automation": 3,
    "cli": 2,
    "web": 2,
    "content": 1,
}


def _clamp(value: int) -> int:
    if value < 0:
        return 0
    if value > 10:
        return 10
    return value


def score_seed(name: str) -> dict:
    seed = require_seed(name)

    internal_value = _clamp(int(seed.get("internal_value", 0)))
    external_value = _clamp(int(seed.get("external_value", 0)))
    complexity = _clamp(int(seed.get("complexity", 0)))
    category = str(seed.get("category", ""))

    strategic_fit = STRATEGIC_FIT_BY_CATEGORY.get(category, 1)

    completeness = 0
    completeness += 1 if str(seed.get("problem", "")).strip() else 0
    completeness += 1 if str(seed.get("target_user", "")).strip() else 0
    completeness += 1 if str(seed.get("title", "")).strip() else 0

    complexity_inverse = 10 - complexity
    total = internal_value + external_value + complexity_inverse + strategic_fit + completeness

    reasons: list[str] = []
    if internal_value >= 7:
        reasons.append("strong internal value")
    if external_value <= 3:
        reasons.append("weak external value")
    if complexity >= 7:
        reasons.append("high complexity risk")
    if completeness < 2:
        reasons.append("seed clarity is low")

    decision_hint = "grow"
    if total < 16:
        decision_hint = "retire"
    elif total < 24:
        decision_hint = "hold"

    return {
        "seed": name,
        "total_score": total,
        "breakdown": {
            "internal_value": internal_value,
            "external_value": external_value,
            "complexity_inverse": complexity_inverse,
            "strategic_fit": strategic_fit,
            "completeness": completeness,
        },
        "reasons": reasons,
        "decision_hint": decision_hint,
    }
