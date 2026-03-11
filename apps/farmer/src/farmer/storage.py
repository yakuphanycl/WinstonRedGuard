from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = APP_ROOT / "data"

FILE_MAP = {
    "seeds": ("seeds.json", "seeds"),
    "growth_jobs": ("growth_jobs.json", "growth_jobs"),
    "harvests": ("harvests.json", "harvests"),
    "warehouse": ("warehouse.json", "warehouse"),
    "decisions": ("decisions.json", "decisions"),
    "activity_log": ("activity_log.json", "activity_log"),
}


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_dir() -> Path:
    # v1 compatibility: FARMER_DATA_PATH points to seeds.json; reuse parent for all files.
    legacy_seed_path = os.environ.get("FARMER_DATA_PATH")
    if legacy_seed_path:
        return Path(legacy_seed_path).resolve().parent
    override = os.environ.get("FARMER_DATA_DIR")
    if override:
        return Path(override).resolve()
    return DEFAULT_DATA_DIR


def _file_and_key(kind: str) -> tuple[Path, str]:
    if kind not in FILE_MAP:
        raise ValueError(f"unknown storage kind: {kind}")
    filename, key = FILE_MAP[kind]
    return data_dir() / filename, key


def ensure_store(kind: str) -> Path:
    path, key = _file_and_key(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({key: []}, indent=2), encoding="utf8")
    return path


def load_rows(kind: str) -> list[dict]:
    path, key = _file_and_key(kind)
    ensure_store(kind)
    payload = json.loads(path.read_text(encoding="utf8"))
    raw = payload.get(key, [])
    return [dict(item) for item in raw if isinstance(item, dict)]


def save_rows(kind: str, rows: list[dict], sort_key: str) -> None:
    path, key = _file_and_key(kind)
    ensure_store(kind)
    ordered = sorted(rows, key=lambda row: str(row.get(sort_key, "")))
    path.write_text(json.dumps({key: ordered}, indent=2, ensure_ascii=False), encoding="utf8")


def append_row(kind: str, row: dict, sort_key: str) -> dict:
    rows = load_rows(kind)
    rows.append(dict(row))
    save_rows(kind, rows, sort_key=sort_key)
    return row


def find_row(kind: str, field: str, value: str) -> dict | None:
    for row in load_rows(kind):
        if row.get(field) == value:
            return row
    return None


def update_row(kind: str, field: str, value: str, updates: dict, sort_key: str) -> dict:
    rows = load_rows(kind)
    for idx, row in enumerate(rows):
        if row.get(field) == value:
            merged = dict(row)
            merged.update(updates)
            merged["updated_at"] = now_iso_utc()
            rows[idx] = merged
            save_rows(kind, rows, sort_key=sort_key)
            return merged
    raise ValueError(f"record not found: {kind}:{value}")
