from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = APP_ROOT / "data" / "refinery_records.json"
LIFECYCLE = {
    "raw",
    "reviewing",
    "refining",
    "packaged",
    "bundled",
    "market_ready_candidate",
    "discarded",
}


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_data_path() -> Path:
    override = os.environ.get("REFINERY_DATA_PATH")
    if override:
        return Path(override)
    return DEFAULT_DATA_PATH


def ensure_store() -> Path:
    path = get_data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"records": []}, indent=2), encoding="utf8")
    return path


def load_records() -> list[dict]:
    path = ensure_store()
    payload = json.loads(path.read_text(encoding="utf8"))
    rows = payload.get("records", [])
    return [dict(row) for row in rows if isinstance(row, dict)]


def save_records(rows: list[dict]) -> None:
    path = ensure_store()
    ordered = sorted(rows, key=lambda row: str(row.get("app_name", "")))
    path.write_text(json.dumps({"records": ordered}, indent=2, ensure_ascii=False), encoding="utf8")


def _default_record(app_name: str) -> dict:
    ts = now_iso_utc()
    return {
        "app_name": app_name,
        "status": "raw",
        "product_score": 0,
        "readme_present": False,
        "cli_present": False,
        "tests_present": False,
        "json_output_present": False,
        "packaging_notes": [],
        "bundle_candidates": [],
        "last_action": "created",
        "created_at": ts,
        "updated_at": ts,
    }


def get_record(app_name: str) -> dict | None:
    for row in load_records():
        if row.get("app_name") == app_name:
            return row
    return None


def get_required_record(app_name: str) -> dict:
    row = get_record(app_name)
    if row is None:
        raise ValueError(f"refinery record not found: {app_name}")
    return row


def upsert_record(app_name: str, updates: dict) -> dict:
    rows = load_records()
    for idx, row in enumerate(rows):
        if row.get("app_name") == app_name:
            merged = dict(row)
            merged.update(updates)
            merged["updated_at"] = now_iso_utc()
            if merged.get("status") not in LIFECYCLE:
                raise ValueError(f"invalid status: {merged.get('status')}")
            rows[idx] = merged
            save_records(rows)
            return merged

    base = _default_record(app_name)
    base.update(updates)
    base["updated_at"] = now_iso_utc()
    if base.get("status") not in LIFECYCLE:
        raise ValueError(f"invalid status: {base.get('status')}")
    rows.append(base)
    save_records(rows)
    return base
