from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .status import inspect_app


def build_system_status(repo_root: Path) -> dict[str, object]:
    apps_dir = repo_root / "apps"
    if not apps_dir.is_dir():
        raise FileNotFoundError(f"apps directory not found: {apps_dir}")

    app_dirs = sorted((p for p in apps_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    apps = [inspect_app(app_dir) for app_dir in app_dirs]

    ok = sum(1 for app in apps if app["status"] == "OK")
    partial = sum(1 for app in apps if app["status"] == "PARTIAL")
    broken = sum(1 for app in apps if app["status"] == "BROKEN")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "apps": len(apps),
            "ok": ok,
            "partial": partial,
            "broken": broken,
        },
        "apps": apps,
    }


def write_json_status(status_report: dict[str, object], json_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(status_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf8",
    )

