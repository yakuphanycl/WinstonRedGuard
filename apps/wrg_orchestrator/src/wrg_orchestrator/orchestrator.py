from __future__ import annotations

from pathlib import Path


WORKFLOW_REGISTRY: dict[str, dict[str, object]] = {
    "daily_check": {
        "name": "daily_check",
        "description": "Scan app structure and summarize health",
        "steps": ["scan_apps", "summarize_health"],
    }
}


def list_workflows() -> list[str]:
    return sorted(WORKFLOW_REGISTRY.keys())


def _inspect_app(app_dir: Path) -> dict[str, object]:
    app_name = app_dir.name
    pyproject_path = app_dir / "pyproject.toml"
    src_package_dir = app_dir / "src" / app_name
    cli_path = src_package_dir / "cli.py"
    tests_dir = app_dir / "tests"

    has_pyproject = pyproject_path.is_file()
    has_src_package = src_package_dir.is_dir()
    has_cli = cli_path.is_file()
    has_tests = tests_dir.is_dir() and any(tests_dir.glob("test_*.py"))

    if has_pyproject and has_src_package and has_cli and has_tests:
        status = "OK"
    elif has_pyproject and has_src_package:
        status = "PARTIAL"
    else:
        status = "BROKEN"

    return {
        "name": app_name,
        "status": status,
        "has_pyproject": has_pyproject,
        "has_src_package": has_src_package,
        "has_cli": has_cli,
        "has_tests": has_tests,
    }


def run_daily_check(repo_root: Path) -> dict[str, object]:
    apps_dir = repo_root / "apps"
    if not apps_dir.is_dir():
        raise FileNotFoundError(f"apps directory not found: {apps_dir}")

    app_dirs = sorted((p for p in apps_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    apps = [_inspect_app(app_dir) for app_dir in app_dirs]

    summary = {
        "apps": len(apps),
        "ok": sum(1 for app in apps if app["status"] == "OK"),
        "partial": sum(1 for app in apps if app["status"] == "PARTIAL"),
        "broken": sum(1 for app in apps if app["status"] == "BROKEN"),
    }

    return {
        "workflow": "daily_check",
        "steps": [
            {"name": "scan_apps", "status": "OK"},
            {"name": "summarize_health", "status": "OK"},
        ],
        "summary": summary,
        "apps": apps,
    }


def run_workflow(workflow_name: str, repo_root: Path) -> dict[str, object]:
    if workflow_name == "daily_check":
        return run_daily_check(repo_root)
    raise ValueError(f"unknown workflow: {workflow_name}")

