from __future__ import annotations

from pathlib import Path


def detect_apps(apps_dir: Path) -> list[str]:
    return sorted(entry.name for entry in apps_dir.iterdir() if entry.is_dir())

