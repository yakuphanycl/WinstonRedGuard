from __future__ import annotations

import importlib
import shutil
import uuid
from pathlib import Path

import pytest

from repo_doctor.core import build_report


def test_import_cli_module() -> None:
    module = importlib.import_module("repo_doctor.cli")
    assert hasattr(module, "main")


@pytest.fixture
def temp_repo_root() -> Path:
    base_tmp = Path(__file__).resolve().parent / ".tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    tmpdir = base_tmp / f"repo_doctor_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=False)
    try:
        yield tmpdir / "repo"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_build_report_classifies_apps(temp_repo_root: Path) -> None:
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

    broken_app = apps_dir / "broken_app"
    broken_app.mkdir()

    report = build_report(repo_root)
    statuses = {app["name"]: app["status"] for app in report["apps"]}

    assert report["total_apps"] == 3
    assert report["ok_count"] == 1
    assert report["partial_count"] == 1
    assert report["broken_count"] == 1
    assert statuses["ok_app"] == "OK"
    assert statuses["partial_app"] == "PARTIAL"
    assert statuses["broken_app"] == "BROKEN"
