from __future__ import annotations

from pathlib import Path

from .core import detect_apps


def _resolve_apps_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "apps"
        if candidate.is_dir():
            return candidate
    return Path("apps")


def main() -> int:
    apps_dir = _resolve_apps_dir()
    if not apps_dir.is_dir():
        print("Error: 'apps' directory was not found.")
        return 1

    apps = detect_apps(apps_dir)
    print("detected apps:")
    for name in apps:
        print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
