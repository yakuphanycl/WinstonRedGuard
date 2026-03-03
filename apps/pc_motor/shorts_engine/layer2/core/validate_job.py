"""
Layer-2 job validation module.

Contract:
  - Exposes a JobValidationError exception type that callers (CLI) can catch
    deterministically.
  - Exposes load_schema() and validate_job() for backwards-compatible imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
from typing import Any, Optional, Dict, List, Union
from .presets import load_preset, PresetError
from .lint_job import lint_job

try:
  # Optional dependency (but recommended). If missing, we still do semantic checks.
  from jsonschema import Draft202012Validator
  from jsonschema.exceptions import ValidationError as _JsonSchemaValidationError
except Exception:  # pragma: no cover
  Draft202012Validator = None
  _JsonSchemaValidationError = Exception

class JobValidationError(Exception):
  """Raised when a Layer-2 job fails validation (schema/semantic checks)."""

__all__ = ["JobValidationError", "load_schema", "validate_job"]

def _schemas_dir() -> Path:
  # shorts_engine/layer2/core/validate_job.py -> shorts_engine/layer2/schemas
  return Path(__file__).resolve().parents[1] / "schemas"

def load_schema(name: Optional[str] = None) -> Dict[str, Any]:
  """
  Load a JSON schema from layer2/schemas/.

  - If name is provided: loads that file (relative to schemas dir).
  - If name is None: best-effort picks a likely schema file.

  Returns: dict schema
  Raises: JobValidationError if schema cannot be found/loaded.
  """
  sd = _schemas_dir()
  if not sd.exists():
    raise JobValidationError(f"schemas dir not found: {sd}")

  if name:
    # Backward-compatible path handling:
    # - absolute/relative file path (e.g. layer2/schemas/job.schema.json)
    # - bare schema filename under schemas dir (e.g. job.schema.json)
    p_in = Path(name)
    candidates = []
    if p_in.is_absolute():
      candidates.append(p_in)
    else:
      candidates.append((Path.cwd() / p_in).resolve())
      candidates.append((sd / p_in).resolve())

    p = next((c for c in candidates if c.exists()), None)
    if p is None:
      raise JobValidationError(f"schema not found: {name}")
    try:
      return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
      raise JobValidationError(f"failed to load schema {p.name}: {type(e).__name__}: {e}")

  # Auto-pick: prefer files containing 'job' and ending with .json
  cands = sorted([p for p in sd.glob("*.json") if "job" in p.name.lower()])
  if not cands:
    # fallback: any json
    cands = sorted(sd.glob("*.json"))
  if not cands:
    raise JobValidationError(f"no schema json files found in: {sd}")

  p = cands[-1]  # pick last (often newest by name sorting)
  try:
    return json.loads(p.read_text(encoding="utf-8-sig"))
  except Exception as e:
    raise JobValidationError(f"failed to load schema {p.name}: {type(e).__name__}: {e}")


def _format_schema_error(e: Exception) -> str:
  """
  Produce human-friendly messages for schema violations.
  """
  # jsonschema ValidationError often has: message, json_path, schema_path
  msg = getattr(e, "message", None) or str(e)
  # instance path is best, fallback to schema path
  path = ""
  try:
    inst_path = list(getattr(e, "absolute_path", []))
    if inst_path:
      path = ".".join(str(x) for x in inst_path)
  except Exception:
    pass
  if path:
    return f"schema error at '{path}': {msg}"
  return f"schema error: {msg}"


def _schema_validate(raw: Dict[str, Any], schema: Dict[str, Any]) -> None:
  """
  Validate using jsonschema if available. Raises JobValidationError on failure.
  """
  if Draft202012Validator is None:
    return  # no jsonschema installed; semantic checks will still run
  v = Draft202012Validator(schema)
  errors = sorted(v.iter_errors(raw), key=lambda e: list(getattr(e, "absolute_path", [])))
  if errors:
    # Show up to 5 errors to keep output readable
    msgs = [_format_schema_error(e) for e in errors[:5]]
    more = "" if len(errors) <= 5 else f"\n(+{len(errors)-5} more)"
    raise JobValidationError("invalid job (schema):\n- " + "\n- ".join(msgs) + more)

def _is_nonempty_str(x: Any) -> bool:
  return isinstance(x, str) and bool(x.strip())


def _semantic_validate(job: Dict[str, Any]) -> None:
  """
  Semantic validation rules (production-safe).
  Raises JobValidationError with human-friendly messages.
  """
  errors: List[str] = []

  preset_name = job.get("preset")
  if preset_name is not None:
    if not _is_nonempty_str(preset_name):
      errors.append("preset must be a non-empty string when provided")
    else:
      try:
        load_preset(str(preset_name).strip())
      except PresetError as e:
        errors.append(str(e))

  # video constraints
  video = job.get("video") if isinstance(job.get("video"), dict) else {}
  fps = video.get("fps")
  if isinstance(fps, int):
    if fps < 24 or fps > 60:
      errors.append("video.fps must be between 24 and 60")
  # duration
  dur = video.get("duration_sec")
  if isinstance(dur, (int, float)):
    if dur <= 0:
      errors.append("video.duration_sec must be > 0")
  # resolution whitelist (v0)
  res = video.get("resolution")
  if isinstance(res, str) and res.strip():
    allowed = {"720x1280", "1080x1920"}
    if res not in allowed:
      errors.append(f"video.resolution must be one of {sorted(allowed)}")

  # subtitles constraints
  subs = job.get("subtitles") if isinstance(job.get("subtitles"), dict) else {}
  items = subs.get("items")
  if isinstance(items, list):
    if len(items) > 120:
      errors.append("subtitles.items is too large (max 120)")
    bad = 0
    for it in items:
      if not isinstance(it, dict) or not _is_nonempty_str(it.get("text")):
        bad += 1
    if bad:
      errors.append(f"subtitles.items contains {bad} invalid item(s) (missing non-empty text)")

  if errors:
    raise JobValidationError("invalid job (semantic):\n- " + "\n- ".join(errors))

def validate_job(raw: Any, schema_name: Optional[Union[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
  """
  Validate a Layer-2 job (minimum contract).

  This function exists primarily to keep CLI imports stable.
  It performs lightweight validation without requiring jsonschema.

  Returns: normalized job dict (raw dict returned as-is for now).
  Raises: JobValidationError on validation failure.
  """
  if not isinstance(raw, dict):
    raise JobValidationError("job must be a JSON object (dict)")

  # 1) Schema validation (if schema exists)
  schema = None
  # Some callers may accidentally pass the schema dict itself here.
  # Be tolerant: if schema_name is a dict, treat it as schema.
  if isinstance(schema_name, dict):
    schema = schema_name
  else:
    # If schema_name is provided but not a string, treat as invalid usage.
    if schema_name is not None and not isinstance(schema_name, str):
      raise JobValidationError(
        f"invalid schema_name type: expected str, got {type(schema_name).__name__}"
      )
    try:
      schema = load_schema(schema_name or "job.v0.json")
    except JobValidationError:
      # If schema missing, we still run semantic validation.
      schema = None
  if schema is not None:
    _schema_validate(raw, schema)

  # 2) Semantic validation (always)
  _semantic_validate(raw)

  # 2.5) Lint validation (default ON, disable with SHORTS_LINT=0|false|off).
  lint_env = str(os.getenv("SHORTS_LINT", "1")).strip().lower()
  lint_enabled = lint_env not in ("0", "false", "off", "no")
  if lint_enabled:
    lint_res = lint_job(raw)
    if not bool(lint_res.get("ok", False)):
      errs = lint_res.get("errors") if isinstance(lint_res.get("errors"), list) else []
      lines: List[str] = []
      for f in errs[:10]:
        if not isinstance(f, dict):
          continue
        lines.append(f"{f.get('code')} {f.get('path')}: {f.get('message')}")
      more = "" if len(errs) <= 10 else f"\n(+{len(errs)-10} more)"
      raise JobValidationError("invalid job (lint):\n- " + "\n- ".join(lines) + more)

  # 3) Normalization (v0: return as-is)
  return raw
