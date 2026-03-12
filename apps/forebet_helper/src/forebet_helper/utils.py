from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def parse_percentage(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d{1,3})(?:[\.,](\d+))?\s*%", value)
    if not match:
        return None
    whole = match.group(1)
    frac = match.group(2) or "0"
    try:
        return float(f"{whole}.{frac}") / 100.0
    except ValueError:
        return None


def normalize_team_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def slugify(value: str | None) -> str:
    if not value:
        return "unknown"
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "unknown"
