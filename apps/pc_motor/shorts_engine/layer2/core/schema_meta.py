from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .version import __version__


def _iso_now() -> str:
    # ISO 8601 with timezone offset
    # If you want local timezone offset, rely on system tz.
    return datetime.now().astimezone().isoformat(timespec="seconds")


def tool_version() -> str:
    return __version__


def schema_meta(schema_version: str) -> Dict[str, Any]:
    return {
        "schema_version": schema_version,
        "generated_at": _iso_now(),
        "tool_version": tool_version(),
    }
