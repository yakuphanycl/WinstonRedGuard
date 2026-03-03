from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(s: str | None) -> str:
    t = str(s or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def idea_key_for(hook: str, body: str, ending: str) -> str:
    base = f"{normalize_text(hook)}|{normalize_text(body)}|{normalize_text(ending)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, obj: Any) -> None:
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        s = raw.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out
