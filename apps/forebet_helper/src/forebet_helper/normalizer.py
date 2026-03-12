from __future__ import annotations

from datetime import datetime, timezone

from .utils import slugify


def build_match_id(home: str | None, away: str | None, kickoff: datetime | None) -> str:
    if kickoff is None:
        date_part = "unknown"
    else:
        if kickoff.tzinfo is None:
            date_part = kickoff.strftime("%Y-%m-%d_%H%M")
        else:
            date_part = kickoff.astimezone(timezone.utc).strftime("%Y-%m-%d_%H%M")
    return f"{slugify(home)}_{slugify(away)}_{date_part}"
