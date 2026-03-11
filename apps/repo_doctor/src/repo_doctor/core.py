from __future__ import annotations

import json
from pathlib import Path

from .doctor import inspect_app


def build_report(repo_root: Path) -> dict[str, object]:
    apps_dir = repo_root / "apps"
    if not apps_dir.is_dir():
        raise FileNotFoundError(f"apps directory not found: {apps_dir}")

    app_dirs = sorted((p for p in apps_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    apps = [inspect_app(app_dir) for app_dir in app_dirs]

    ok_count = sum(1 for app in apps if app["status"] == "OK")
    partial_count = sum(1 for app in apps if app["status"] == "PARTIAL")
    broken_count = sum(1 for app in apps if app["status"] == "BROKEN")

    return {
        "total_apps": len(apps),
        "ok_count": ok_count,
        "partial_count": partial_count,
        "broken_count": broken_count,
        "apps": apps,
    }


def write_json_report(report: dict[str, object], json_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf8")

