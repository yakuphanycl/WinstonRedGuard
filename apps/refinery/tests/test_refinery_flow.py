from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest

from refinery import cli
from refinery.core import load_records


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


def _create_app(repo_root: Path, app_name: str, *, readme: bool = True, tests: bool = True, cli_file: bool = True, json_signal: bool = False) -> None:
    app = repo_root / "apps" / app_name
    app.mkdir(parents=True, exist_ok=True)
    if readme:
        content = "# app\n"
        if json_signal:
            content += "supports --json-out\n"
        _write(app / "README.md", content)
    _write(app / "pyproject.toml", "[project]\nname='x'\n")
    _write(app / "src" / app_name / "__init__.py", "")
    if cli_file:
        code = "def main():\n    return 0\n"
        if json_signal:
            code += "# json output\n"
        _write(app / "src" / app_name / "cli.py", code)
    if tests:
        _write(app / "tests" / "test_smoke.py", "def test_x():\n    assert True\n")


@pytest.fixture
def isolated_env() -> Path:
    base_tmp = Path(__file__).resolve().parent / ".tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    tmpdir = base_tmp / f"refinery_{uuid.uuid4().hex}"
    repo_root = tmpdir / "repo"
    repo_root.mkdir(parents=True, exist_ok=False)

    data_path = tmpdir / "refinery_records.json"
    old_data = os.environ.get("REFINERY_DATA_PATH")
    old_cwd = Path.cwd()

    os.environ["REFINERY_DATA_PATH"] = str(data_path)
    os.chdir(repo_root)
    try:
        yield repo_root
    finally:
        os.chdir(old_cwd)
        if old_data is None:
            os.environ.pop("REFINERY_DATA_PATH", None)
        else:
            os.environ["REFINERY_DATA_PATH"] = old_data
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_inspect_success(isolated_env: Path) -> None:
    _create_app(isolated_env, "alpha_app", json_signal=True)

    exit_code = cli.main(["inspect", "alpha_app"])
    assert exit_code == 0

    row = load_records()[0]
    assert row["app_name"] == "alpha_app"
    assert row["status"] == "reviewing"
    assert row["product_score"] == 4
    assert row["json_output_present"] is True


def test_inspect_non_existing_app_fails(isolated_env: Path) -> None:
    exit_code = cli.main(["inspect", "ghost_app"])
    assert exit_code == 1


def test_refine_plan_suggestions(isolated_env: Path) -> None:
    _create_app(isolated_env, "beta_app", readme=False, tests=False, cli_file=False, json_signal=False)
    assert cli.main(["inspect", "beta_app"]) == 0

    exit_code = cli.main(["refine-plan", "beta_app"])
    assert exit_code == 0

    row = load_records()[0]
    assert row["status"] == "refining"
    assert "README ekle" in row["packaging_notes"]
    assert "smoke test ekle" in row["packaging_notes"]
    assert "entry CLI olustur" in row["packaging_notes"]
    assert "machine-readable cikti ekle" in row["packaging_notes"]


def test_package_mark_transitions(isolated_env: Path) -> None:
    _create_app(isolated_env, "gamma_app")
    assert cli.main(["inspect", "gamma_app"]) == 0

    assert cli.main(["package-mark", "gamma_app"]) == 0
    row = load_records()[0]
    assert row["status"] == "packaged"

    assert cli.main(["package-mark", "gamma_app", "--market-ready"]) == 0
    row = load_records()[0]
    assert row["status"] == "market_ready_candidate"


def test_bundle_suggest_updates_candidates(isolated_env: Path) -> None:
    _create_app(isolated_env, "refinery")
    assert cli.main(["inspect", "refinery"]) == 0

    exit_code = cli.main(["bundle-suggest", "refinery"])
    assert exit_code == 0

    row = load_records()[0]
    assert row["bundle_candidates"] == ["farmer"]
    assert row["status"] == "bundled"
