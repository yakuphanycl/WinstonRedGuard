from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/144.0.0.0 Safari/537.36"
    )
    timeout_seconds: int = 20
    min_delay_seconds: float = 3.0
    max_delay_seconds: float = 8.0
    cache_ttl_seconds: int = 6 * 60 * 60
    cache_dir: Path = Path("data/cache")
