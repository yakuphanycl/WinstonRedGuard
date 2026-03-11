from __future__ import annotations

from .core import get_required_record, upsert_record


def mark_packaged(app_name: str, market_ready: bool = False) -> dict:
    _ = get_required_record(app_name)
    next_status = "market_ready_candidate" if market_ready else "packaged"
    return upsert_record(
        app_name,
        {
            "status": next_status,
            "last_action": "package-mark",
        },
    )
