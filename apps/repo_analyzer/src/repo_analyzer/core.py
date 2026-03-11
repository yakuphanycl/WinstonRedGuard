from __future__ import annotations

from pathlib import Path


def detect_apps(repo_root: Path) -> list[str]:
    apps_dir = repo_root / "apps"

    if not apps_dir.exists() or not apps_dir.is_dir():
        raise FileNotFoundError(f"apps directory not found: {apps_dir}")

    app_names = [item.name for item in apps_dir.iterdir() if item.is_dir()]
    return sorted(app_names)


def check_apps(repo_root: Path) -> list[tuple[str, str]]:
    apps_dir = repo_root / "apps"

    if not apps_dir.exists() or not apps_dir.is_dir():
        raise FileNotFoundError(f"apps directory not found: {apps_dir}")

    results: list[tuple[str, str]] = []

    for app_dir in sorted((p for p in apps_dir.iterdir() if p.is_dir()), key=lambda p: p.name):
        name = app_dir.name
        missing: list[str] = []

        if not (app_dir / "README.md").exists():
            missing.append("README")

        if not (app_dir / "tests").exists():
            missing.append("tests")

        if not (app_dir / "pyproject.toml").exists():
            missing.append("pyproject")

        cli_path = app_dir / "src" / name / "cli.py"
        if not cli_path.exists():
            missing.append("cli")

        status = "OK" if not missing else "MISSING " + ",".join(missing)
        results.append((name, status))

    return results