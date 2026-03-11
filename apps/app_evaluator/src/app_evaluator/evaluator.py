from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _has_main_function(cli_path: Path) -> bool:
    if not cli_path.exists():
        return False
    text = cli_path.read_text(encoding="utf8")
    return "def main(" in text


def _run_pytest(app_path: Path) -> tuple[bool, str, int]:
    tests_dir = app_path / "tests"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output, result.returncode


def evaluate_app(app_path: Path) -> dict:
    app_name = app_path.name
    cli_path = app_path / "src" / app_name / "cli.py"

    checks: dict[str, bool] = {}
    checks["app_exists"] = app_path.exists() and app_path.is_dir()
    checks["pyproject_exists"] = (app_path / "pyproject.toml").exists()
    checks["cli_exists"] = _has_main_function(cli_path)
    checks["tests_exist"] = (app_path / "tests").exists()
    checks["smoke_test_exists"] = (app_path / "tests" / "test_smoke.py").exists()

    pytest_passed, pytest_output, pytest_exit_code = _run_pytest(app_path)
    checks["pytest_passed"] = pytest_passed

    score = sum(1 for ok in checks.values() if ok)
    ok = all(checks.values())

    return {
        "app_name": app_name,
        "ok": ok,
        "checks": checks,
        "score": score,
        "evaluated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "pytest": {
            "exit_code": pytest_exit_code,
            "stdout": pytest_output,
        },
    }


def write_report(report: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
