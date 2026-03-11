from __future__ import annotations

from pathlib import Path


def inspect_app(app_dir: Path) -> dict[str, object]:
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

