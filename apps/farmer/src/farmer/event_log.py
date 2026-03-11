from __future__ import annotations

import json
from pathlib import Path

from .storage import data_dir, now_iso_utc

EVENT_FILE = "activity_log.json"
EVENT_KEY = "activity_log"


def _event_path() -> Path:
    return data_dir() / EVENT_FILE


def _ensure_store() -> Path:
    path = _event_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({EVENT_KEY: []}, indent=2), encoding="utf8")
    return path


def _load_all() -> list[dict]:
    path = _ensure_store()
    payload = json.loads(path.read_text(encoding="utf8"))
    rows = payload.get(EVENT_KEY, [])
    return [dict(item) for item in rows if isinstance(item, dict)]


def _save_all(rows: list[dict]) -> None:
    path = _ensure_store()
    path.write_text(json.dumps({EVENT_KEY: rows}, indent=2, ensure_ascii=False), encoding="utf8")


def _normalize_payload(payload: dict) -> dict:
    return {key: payload[key] for key in sorted(payload.keys())}


def append_event(event_type: str, seed_name: str, payload: dict) -> dict:
    event = {
        "event_type": event_type,
        "seed_name": seed_name,
        "timestamp": now_iso_utc(),
        "payload": _normalize_payload(dict(payload)),
    }
    rows = _load_all()
    rows.append(event)
    _save_all(rows)
    return event


def list_events(seed_name: str | None = None) -> list[dict]:
    rows = _load_all()
    if seed_name is None:
        return rows
    return [row for row in rows if row.get("seed_name") == seed_name]


def recent_events(seed_name: str, limit: int = 5) -> list[dict]:
    rows = list_events(seed_name=seed_name)
    if limit <= 0:
        return []
    if len(rows) <= limit:
        return list(reversed(rows))
    return list(reversed(rows[-limit:]))
