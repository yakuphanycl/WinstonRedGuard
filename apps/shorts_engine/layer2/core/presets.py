from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PRESET_SCHEMA_VERSION = "0.1"
MERGE_SECTIONS = ("video", "subtitles", "visual", "voice")


class PresetError(Exception):
    pass


def presets_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "presets"


def list_presets() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    d = presets_dir()
    if not d.exists() or not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
            if not isinstance(obj, dict):
                continue
            name = obj.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            desc = obj.get("description")
            out.append(
                {
                    "name": name.strip(),
                    "description": str(desc).strip() if isinstance(desc, str) else "",
                    "path": str(p),
                }
            )
        except Exception:
            continue
    return out


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def preset_hash(preset_obj: dict[str, Any]) -> str:
    return hashlib.sha1(_stable_json(preset_obj).encode("utf-8")).hexdigest()


def load_preset(name: str) -> dict[str, Any]:
    nm = str(name or "").strip()
    if not nm:
        raise PresetError("preset name is empty")
    p = presets_dir() / f"{nm}.json"
    if not p.exists() or not p.is_file():
        raise PresetError(f"unknown preset: {nm}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise PresetError(f"failed to read preset {nm}: {e}") from e
    if not isinstance(obj, dict):
        raise PresetError(f"invalid preset root: {nm}")
    sv = obj.get("schema_version")
    if str(sv) != PRESET_SCHEMA_VERSION:
        raise PresetError(f"invalid preset schema_version for {nm}: expected {PRESET_SCHEMA_VERSION}, got {sv}")
    pname = obj.get("name")
    if str(pname) != nm:
        raise PresetError(f"preset name mismatch: file={nm}.json name={pname}")
    return obj


def _deep_merge_defaults(base: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(defaults)
    for k, v in base.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_defaults(v, out.get(k) or {})
        else:
            out[k] = v
    return out


def apply_preset(raw_job: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None]:
    if not isinstance(raw_job, dict):
        raise PresetError("job must be object")
    preset_name = raw_job.get("preset")
    if not isinstance(preset_name, str) or not preset_name.strip():
        return dict(raw_job), None, None

    preset = load_preset(preset_name.strip())
    ph = preset_hash(preset)
    effective = dict(raw_job)
    for sec in MERGE_SECTIONS:
        pv = preset.get(sec)
        jv = effective.get(sec)
        if isinstance(pv, dict):
            if isinstance(jv, dict):
                effective[sec] = _deep_merge_defaults(jv, pv)
            elif jv is None:
                effective[sec] = dict(pv)
    return effective, preset_name.strip(), ph

