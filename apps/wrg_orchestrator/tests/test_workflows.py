from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from wrg_orchestrator.core import execute_workflow, get_workflows


@pytest.fixture
def temp_repo_root() -> Path:
    base_tmp = Path(__file__).resolve().parent / ".tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    tmpdir = base_tmp / f"wrg_orchestrator_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=False)
    try:
        yield tmpdir / "repo"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_list_contains_daily_check() -> None:
    workflows = get_workflows()
    assert "daily_check" in workflows


def test_run_daily_check_expected_keys(temp_repo_root: Path) -> None:
    repo_root = temp_repo_root
    apps_dir = repo_root / "apps"
    apps_dir.mkdir(parents=True)

    ok_app = apps_dir / "ok_app"
    (ok_app / "src" / "ok_app").mkdir(parents=True)
    (ok_app / "tests").mkdir()
    (ok_app / "pyproject.toml").write_text("[project]\nname='ok_app'\n", encoding="utf8")
    (ok_app / "src" / "ok_app" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf8")
    (ok_app / "tests" / "test_smoke.py").write_text("def test_x():\n    assert True\n", encoding="utf8")

    partial_app = apps_dir / "partial_app"
    (partial_app / "src" / "partial_app").mkdir(parents=True)
    (partial_app / "pyproject.toml").write_text("[project]\nname='partial_app'\n", encoding="utf8")

    result = execute_workflow("daily_check", repo_root)

    assert result["workflow"] == "daily_check"
    assert "generated_at" in result
    assert "steps" in result
    assert "summary" in result
    assert "apps" in result
    assert result["summary"]["apps"] == 2
    assert result["summary"]["ok"] == 1
    assert result["summary"]["partial"] == 1
    assert result["summary"]["broken"] == 0

