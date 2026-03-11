from __future__ import annotations

from .event_log import append_event
from .seed_bank import require_seed, set_status
from .storage import find_row, load_rows, now_iso_utc, save_rows, update_row

VALID_BUCKETS = {"internal_stock", "external_candidates", "refine_queue", "cold_storage", "retired"}


def validate_bucket(bucket: str) -> None:
    if bucket not in VALID_BUCKETS:
        raise ValueError(
            "invalid warehouse bucket: choose internal_stock, external_candidates, "
            "refine_queue, cold_storage, retired"
        )


def _ensure_entry(seed_name: str) -> dict:
    existing = find_row("warehouse", "name", seed_name)
    if existing is not None:
        return existing
    ts = now_iso_utc()
    row = {
        "name": seed_name,
        "bucket": "internal_stock",
        "created_at": ts,
        "updated_at": ts,
    }
    rows = load_rows("warehouse")
    rows.append(row)
    save_rows("warehouse", rows, sort_key="name")
    return row


def store_harvested(seed_name: str) -> dict:
    seed = require_seed(seed_name)
    if seed.get("status") != "harvested":
        raise ValueError(f"seed is not harvested: {seed_name}")
    existing = _ensure_entry(seed_name)
    if existing.get("bucket") == "internal_stock":
        set_status(seed_name, "stored")
        return existing
    set_status(seed_name, "stored")
    return update_row("warehouse", "name", seed_name, {"bucket": "internal_stock"}, sort_key="name")


def warehouse_list() -> list[dict]:
    return load_rows("warehouse")


def warehouse_show(seed_name: str) -> dict:
    row = find_row("warehouse", "name", seed_name)
    if row is None:
        raise ValueError(f"warehouse record not found: {seed_name}")
    return row


def warehouse_move(seed_name: str, bucket: str) -> dict:
    validate_bucket(bucket)
    _ = require_seed(seed_name)
    row = _ensure_entry(seed_name)
    current_bucket = str(row.get("bucket", ""))
    if current_bucket == bucket:
        return row

    result = update_row("warehouse", "name", seed_name, {"bucket": bucket}, sort_key="name")
    if bucket == "retired":
        set_status(seed_name, "retired")
    elif current_bucket == "retired" and bucket != "retired":
        set_status(seed_name, "stored")

    append_event("warehouse_moved", seed_name, {"bucket": bucket})
    return result
