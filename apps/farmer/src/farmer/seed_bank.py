from __future__ import annotations

from .event_log import append_event
from .storage import find_row, load_rows, now_iso_utc, save_rows, update_row

LIFECYCLE_STATES = {
    "seed",
    "scored",
    "queued",
    "sprout",
    "growing",
    "maturing",
    "harvestable",
    "harvested",
    "stored",
    "hold",
    "retired",
    "composted",
}

VALID_CATEGORIES = {"cli", "web", "content", "infra", "automation"}
VALID_TRANSITIONS = {
    "seed": {"scored", "queued", "hold", "retired", "composted"},
    "scored": {"queued", "sprout", "hold", "retired", "composted"},
    "queued": {"sprout", "hold", "retired", "composted"},
    "sprout": {"growing", "hold", "retired", "composted"},
    "growing": {"maturing", "hold", "retired", "composted"},
    "maturing": {"harvestable", "hold", "retired", "composted"},
    "harvestable": {"harvested", "hold", "retired", "composted"},
    "harvested": {"stored", "retired"},
    "stored": {"hold", "retired"},
    "hold": {"queued", "retired", "composted", "scored"},
    "retired": {"stored"},
    "composted": set(),
}


def _require_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")


def _require_score_input(value: int, field: str) -> None:
    if not isinstance(value, int) or value < 0 or value > 10:
        raise ValueError(f"{field} must be an integer between 0 and 10")


def find_seed(name: str) -> dict | None:
    return find_row("seeds", "name", name)


def load_seeds() -> list[dict]:
    return load_rows("seeds")


def add_seed(
    name: str,
    title: str | None,
    category: str,
    problem: str,
    target_user: str,
    internal_value: int,
    external_value: int,
    complexity: int,
) -> dict:
    _require_name(name)
    _require_score_input(internal_value, "internal_value")
    _require_score_input(external_value, "external_value")
    _require_score_input(complexity, "complexity")

    if category not in VALID_CATEGORIES:
        raise ValueError("category must be one of: cli, web, content, infra, automation")

    rows = load_seeds()
    if any(row.get("name") == name for row in rows):
        raise ValueError(f"seed already exists: {name}")

    ts = now_iso_utc()
    record = {
        "name": name,
        "title": title or "",
        "category": category,
        "problem": problem,
        "target_user": target_user,
        "internal_value": internal_value,
        "external_value": external_value,
        "complexity": complexity,
        "status": "seed",
        "score": None,
        "score_breakdown": None,
        "score_reasons": [],
        "decision_hint": None,
        "created_at": ts,
        "updated_at": ts,
    }
    rows.append(record)
    save_rows("seeds", rows, sort_key="name")
    append_event("seed_added", name, {"status": "seed"})
    return record


def require_seed(name: str) -> dict:
    row = find_seed(name)
    if row is None:
        raise ValueError(f"seed not found: {name}")
    return row


def set_status(name: str, status: str, extra: dict | None = None) -> dict:
    if status not in LIFECYCLE_STATES:
        raise ValueError(f"invalid lifecycle status: {status}")
    current = str(require_seed(name).get("status", ""))
    if current != status:
        allowed = VALID_TRANSITIONS.get(current, set())
        if status not in allowed:
            allowed_text = ", ".join(sorted(allowed)) if allowed else "none"
            raise ValueError(
                f"invalid lifecycle transition: {current} -> {status} "
                f"(allowed: {allowed_text})"
            )
    payload = {"status": status}
    if extra:
        payload.update(extra)
    return update_row("seeds", "name", name, payload, sort_key="name")


def set_score_result(name: str, result: dict) -> dict:
    row = set_status(
        name,
        "scored",
        extra={
            "score": result["total_score"],
            "score_breakdown": result["breakdown"],
            "score_reasons": result["reasons"],
            "decision_hint": result["decision_hint"],
        },
    )
    append_event(
        "score_result_set",
        name,
        {
            "score": int(result["total_score"]),
            "result": str(result["decision_hint"]),
        },
    )
    return row
