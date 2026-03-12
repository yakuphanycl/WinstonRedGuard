from __future__ import annotations

import json
from pathlib import Path
from time import time

from .utils import sha256_text


class SimpleFileCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        digest = sha256_text(key)
        return self.cache_dir / f"{digest}.json"

    def get(self, key: str, ttl_seconds: int) -> str | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ts = float(payload["ts"])
            content = str(payload["content"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            return None

        if time() - ts > ttl_seconds:
            return None
        return content

    def set(self, key: str, content: str) -> None:
        path = self._path_for(key)
        payload = {"ts": time(), "content": content}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
