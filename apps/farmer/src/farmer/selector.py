from __future__ import annotations

from .event_log import append_event
from .seed_bank import require_seed
from .storage import append_row, find_row, load_rows, now_iso_utc, update_row
from .warehouse import VALID_BUCKETS, warehouse_show

SELECTABLE_STATUSES = {"harvested", "stored", "maturing", "harvestable", "hold", "retired", "composted"}


def _build_decision(seed: dict, bucket: str | None) -> tuple[str, str, bool, list[str]]:
    score = int(seed.get("score") or 0)
    internal = int(seed.get("internal_value", 0))
    external = int(seed.get("external_value", 0))
    status = str(seed.get("status", ""))

    reason_codes: list[str] = ["status_allowed"]
    if seed.get("score") is None:
        reason_codes.append("score_missing")
    else:
        reason_codes.append("score_present")

    if bucket is None:
        pass
    elif bucket not in VALID_BUCKETS:
        reason_codes.append("bucket_invalid")
    elif bucket == "external_candidates":
        reason_codes.append("bucket_match")

    decision = "hold"
    reason = "default hold"
    selected = False

    if status in {"retired", "composted"}:
        decision = "retire"
        reason = "lifecycle is retired/composted"
        selected = False
    elif bucket == "external_candidates" and score >= 26 and external >= 7:
        decision = "promote_external"
        reason = "strong score and external value"
        selected = True
    elif score >= 24 and internal >= 7:
        decision = "hire_internal"
        reason = "strong score and internal value"
        selected = True
    elif bucket == "refine_queue" or score < 24:
        decision = "send_to_refinery"
        reason = "needs refinement before promotion"
        selected = True

    return decision, reason, selected, reason_codes


def select_seed(name: str) -> dict:
    seed = require_seed(name)
    status = str(seed.get("status", ""))
    if status not in SELECTABLE_STATUSES:
        allowed_text = ", ".join(sorted(SELECTABLE_STATUSES))
        raise ValueError(
            f"invalid lifecycle state for select: {status} (allowed: {allowed_text})"
        )

    try:
        wh = warehouse_show(name)
        bucket = wh.get("bucket")
    except ValueError:
        bucket = None

    decision, reason, selected, reason_codes = _build_decision(seed, bucket)
    score = int(seed.get("score") or 0)
    ts = now_iso_utc()

    record = {
        "name": name,
        "decision": decision,
        "reason": reason,
        "selected": selected,
        "reason_codes": reason_codes,
        "score": score,
        "status": status,
        "bucket": bucket,
        "created_at": ts,
        "updated_at": ts,
    }

    existing = find_row("decisions", "name", name)
    if existing is None:
        append_row("decisions", record, sort_key="name")
        append_event("seed_selected", name, {"selected": selected, "reason_codes": reason_codes})
        return record

    unchanged = (
        existing.get("decision") == decision
        and existing.get("reason") == reason
        and bool(existing.get("selected")) == selected
        and list(existing.get("reason_codes", [])) == reason_codes
        and existing.get("status") == status
        and existing.get("bucket") == bucket
        and int(existing.get("score") or 0) == score
    )
    if unchanged:
        return existing

    merged = update_row("decisions", "name", name, record, sort_key="name")
    append_event("seed_selected", name, {"selected": selected, "reason_codes": reason_codes})
    return merged


def list_decisions() -> list[dict]:
    return load_rows("decisions")


def latest_decision(name: str) -> dict | None:
    return find_row("decisions", "name", name)
