from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from governance_check import cli
from governance_check.core import run_check


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


def _create_valid_app(
    repo_root: Path,
    name: str,
    *,
    with_tests: bool = True,
    with_cli: bool = True,
    readme_text: str | None = None,
    json_signal: bool = True,
) -> Path:
    app = repo_root / "apps" / name
    content = readme_text if readme_text is not None else f"# {name}\nproduct --json-out\n"
    _write(app / "README.md", content)
    _write(app / "pyproject.toml", "[project]\nname='x'\n")
    _write(app / "src" / name / "__init__.py", "")
    if with_cli:
        cli_text = "def main():\n    return 0\n"
        if json_signal:
            cli_text += "# supports --json-out\n"
        _write(app / "src" / name / "cli.py", cli_text)
    if with_tests:
        _write(app / "tests" / "test_smoke.py", "def test_ok():\n    assert True\n")
    return app


def _create_node_app(repo_root: Path, name: str, *, with_tests: bool = True) -> Path:
    app = repo_root / "apps" / name
    _write(app / "README.md", f"# {name}\nnode dashboard\n")
    _write(app / "package.json", '{"name": "' + name + '"}\n')
    if with_tests:
        _write(app / "tests" / "test_smoke.js", "console.log('ok');\n")
    return app


def _base_entry(name: str, app_path: Path, **overrides: object) -> dict:
    payload = {
        "name": name,
        "version": "0.1.0",
        "role": "worker",
        "entrypoint": f"{name}.cli:main",
        "status": "active",
        "verified": True,
        "score": 7,
        "app_path": str(app_path),
        "class": "worker",
        "primary_role": "ops worker",
        "internal_customer": "ops",
        "external_product_potential": "medium",
        "productization_stage": "internal_operational",
        "class_assigned_at": "2026-03-08T00:00:00+00:00",
        "class_assigned_by": "human",
        "reclassification_reason": None,
        "reclassification_history": [],
    }
    payload.update(overrides)
    return payload


def _write_docs(repo_root: Path, app_names: list[str]) -> None:
    merged = sorted(set(app_names) | {"app_registry"})
    systems = "\n".join([f"| `{name}` | apps/{name} | role |" for name in merged])
    text = "# Docs\n\n| System | Location | Purpose |\n|---|---|---|\n" + systems + "\n"
    _write(repo_root / "company_map.md", text)
    _write(repo_root / "AGENT_CONTEXT.md", text)


def _write_registry(repo_root: Path, apps: list[dict]) -> None:
    app_registry_path = _create_valid_app(repo_root, "app_registry")
    entries = list(apps)
    if not any(entry.get("name") == "app_registry" for entry in entries):
        entries.append(
            _base_entry(
                "app_registry",
                app_registry_path,
                role="registry",
                primary_role="registry authority",
                internal_customer=["all apps"],
                external_product_potential="medium",
                **{"class": "internal_infra"},
            )
        )
    path = repo_root / "apps" / "app_registry" / "data" / "registry.json"
    _write(path, json.dumps({"apps": entries}, indent=2))


@pytest.fixture
def temp_repo_root() -> Path:
    base_tmp = Path(__file__).resolve().parent / ".tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    tmpdir = base_tmp / f"governance_check_{uuid.uuid4().hex}"
    repo_root = tmpdir / "repo"
    repo_root.mkdir(parents=True, exist_ok=False)
    try:
        yield repo_root
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_success_minimal_valid_repo(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "worker_one")
    _write_docs(temp_repo_root, ["worker_one"])
    _write_registry(temp_repo_root, [_base_entry("worker_one", app)])

    report = run_check(temp_repo_root)
    assert report["error"] == 0
    assert report["warning"] == 0
    assert report["overall"] == "PASS"


def test_docs_parser_ignores_metadata_field_tokens(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "real_worker")
    docs_text = """# Docs

| System | Location | Purpose |
|---|---|---|
| `real_worker` | apps/real_worker | role |
| `class` | n/a | metadata |
| `primary_role` | n/a | metadata |
| `internal_customer` | n/a | metadata |
| `external_product_potential` | n/a | metadata |
| `productization_stage` | n/a | metadata |
| `worker` | n/a | metadata |
"""
    _write(temp_repo_root / "company_map.md", docs_text)
    _write(temp_repo_root / "AGENT_CONTEXT.md", docs_text)
    _write_registry(temp_repo_root, [_base_entry("real_worker", app)])

    report = run_check(temp_repo_root)
    blocked = {
        "class",
        "worker",
        "primary_role",
        "productization_stage",
        "internal_customer",
        "external_product_potential",
    }
    listed_apps = {row["app"] for row in report["checks"]}
    assert blocked.isdisjoint(listed_apps)


def test_docs_worker_not_found_still_reported_for_real_identifier(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "real_worker")
    docs_text = """# Docs

| System | Location | Purpose |
|---|---|---|
| `real_worker` | apps/real_worker | role |
| `ghost_worker` | apps/ghost_worker | role |
"""
    _write(temp_repo_root / "company_map.md", docs_text)
    _write(temp_repo_root / "AGENT_CONTEXT.md", docs_text)
    _write_registry(temp_repo_root, [_base_entry("real_worker", app)])

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "ghost_worker")
    assert any(f["code"] == "DOCS_WORKER_NOT_FOUND" for f in row["findings"])


def test_flat_python_layout_with_project_scripts_passes_structure_checks(temp_repo_root: Path) -> None:
    app = temp_repo_root / "apps" / "workspace_inspector"
    _write(app / "README.md", "# workspace_inspector\nops worker --json-out\n")
    _write(
        app / "pyproject.toml",
        "[project]\nname='workspace-inspector'\n[project.scripts]\nworkspace-inspector='workspace_inspector.cli.main:main'\n",
    )
    _write(app / "workspace_inspector" / "__init__.py", "")
    _write(app / "workspace_inspector" / "cli" / "main.py", "def main():\n    return 0\n")
    _write(app / "tests" / "test_smoke.py", "def test_ok():\n    assert True\n")
    _write_docs(temp_repo_root, ["workspace_inspector"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "workspace_inspector",
                app,
                entrypoint="workspace_inspector.cli.main:main",
                app_type="python_app",
                layout="flat",
                python_package="workspace_inspector",
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "workspace_inspector")
    assert all(
        f["code"] not in {"MISSING_PYPROJECT", "MISSING_SRC_PACKAGE", "MISSING_CLI_AND_ENTRYPOINT"}
        for f in row["findings"]
    )


def test_node_app_skips_python_specific_required_structure_rules(temp_repo_root: Path) -> None:
    app = _create_node_app(temp_repo_root, "wrg_dashboard")
    _write_docs(temp_repo_root, ["wrg_dashboard"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "wrg_dashboard",
                app,
                role="dashboard",
                entrypoint="npm run dev:desktop",
                app_type="node_app",
                layout="custom",
                stack="electron-vite",
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "wrg_dashboard")
    assert all(
        f["code"] not in {"MISSING_PYPROJECT", "MISSING_SRC_PACKAGE", "MISSING_CLI_AND_ENTRYPOINT"}
        for f in row["findings"]
    )


def test_legacy_flat_missing_cli_and_entrypoint_is_warning(temp_repo_root: Path) -> None:
    app = temp_repo_root / "apps" / "pc_motor"
    _write(app / "README.md", "# pc_motor\nlegacy worker\n")
    _write(app / "pyproject.toml", "[project]\nname='pc_motor'\n")
    _write(app / "pc_motor" / "__init__.py", "")
    _write(app / "tests" / "test_smoke.py", "def test_ok():\n    assert True\n")
    _write_docs(temp_repo_root, ["pc_motor"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "pc_motor",
                app,
                entrypoint="",
                app_type="python_app",
                layout="legacy_flat",
                python_package="pc_motor",
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "pc_motor")
    finding = next(f for f in row["findings"] if f["code"] == "MISSING_CLI_AND_ENTRYPOINT")
    assert finding["severity"] == "WARNING"


def test_custom_layout_missing_classic_package_is_warning(temp_repo_root: Path) -> None:
    app = temp_repo_root / "apps" / "shorts_engine"
    _write(app / "README.md", "# shorts_engine\ncustom worker\n")
    _write(app / "pyproject.toml", "[project]\nname='shorts_engine'\n")
    _write(app / "layer2" / "cli" / "plan.py", "def main():\n    return 0\n")
    _write(app / "tests" / "test_smoke.py", "def test_ok():\n    assert True\n")
    _write_docs(temp_repo_root, ["shorts_engine"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "shorts_engine",
                app,
                entrypoint="",
                app_type="python_app",
                layout="custom",
                python_package="shorts_engine",
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "shorts_engine")
    finding = next(f for f in row["findings"] if f["code"] == "MISSING_SRC_PACKAGE")
    assert finding["severity"] == "WARNING"


def test_python_package_override_for_src_layout(temp_repo_root: Path) -> None:
    app = temp_repo_root / "apps" / "yyfe_lab"
    _write(app / "README.md", "# yyfe_lab\nops worker --json-out\n")
    _write(app / "pyproject.toml", "[project]\nname='yyfe-lab'\n")
    _write(app / "src" / "yyfe" / "__init__.py", "")
    _write(app / "src" / "yyfe" / "cli.py", "def main():\n    return 0\n")
    _write(app / "tests" / "test_smoke.py", "def test_ok():\n    assert True\n")
    _write_docs(temp_repo_root, ["yyfe_lab"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "yyfe_lab",
                app,
                entrypoint="yyfe.cli:main",
                app_type="python_app",
                layout="src",
                python_package="yyfe",
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "yyfe_lab")
    assert all(f["code"] not in {"MISSING_SRC_PACKAGE", "MISSING_CLI_AND_ENTRYPOINT"} for f in row["findings"])


def test_missing_class_yields_warning(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "classless")
    _write_docs(temp_repo_root, ["classless"])
    entry = _base_entry("classless", app)
    entry.pop("class")
    _write_registry(temp_repo_root, [entry])

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "classless")
    assert row["level"] == "WARNING"
    assert any(f["code"] == "CLASS_MISSING" for f in row["findings"])


def test_invalid_class_is_error(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "invalid_class")
    _write_docs(temp_repo_root, ["invalid_class"])
    _write_registry(temp_repo_root, [_base_entry("invalid_class", app, **{"class": "invalid"})])

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "invalid_class")
    assert row["level"] == "ERROR"
    assert any(f["code"] == "CLASS_INVALID" for f in row["findings"])


def test_dual_role_missing_tests_is_error(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "dual_no_tests", with_tests=False)
    _write_docs(temp_repo_root, ["dual_no_tests"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "dual_no_tests",
                app,
                **{
                    "class": "dual_role_product",
                    "productization_stage": "product_candidate",
                    "reclassification_history": [{"from": "worker", "to": "dual_role_product", "at": "2026-03-08T00:00:00+00:00", "by": "human", "reason": "promotion"}],
                    "reclassification_reason": "promotion",
                },
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "dual_no_tests")
    assert any(f["code"] == "DUAL_ROLE_TESTS_REQUIRED" for f in row["findings"])
    assert row["level"] == "ERROR"


def test_dual_role_missing_cli_is_error(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "dual_no_cli", with_cli=False)
    _write_docs(temp_repo_root, ["dual_no_cli"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "dual_no_cli",
                app,
                **{
                    "class": "dual_role_product",
                    "entrypoint": "dual_no_cli.cli:main",
                    "productization_stage": "product_candidate",
                    "reclassification_history": [{"from": "worker", "to": "dual_role_product", "at": "2026-03-08T00:00:00+00:00", "by": "human", "reason": "promotion"}],
                    "reclassification_reason": "promotion",
                },
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "dual_no_cli")
    assert any(f["code"] == "DUAL_ROLE_CLI_REQUIRED" for f in row["findings"])


def test_dual_role_low_stage_is_error(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "dual_low_stage")
    _write_docs(temp_repo_root, ["dual_low_stage"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "dual_low_stage",
                app,
                **{
                    "class": "dual_role_product",
                    "productization_stage": "internal_mvp",
                    "reclassification_history": [{"from": "worker", "to": "dual_role_product", "at": "2026-03-08T00:00:00+00:00", "by": "human", "reason": "promotion"}],
                    "reclassification_reason": "promotion",
                },
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "dual_low_stage")
    assert any(f["code"] == "DUAL_ROLE_STAGE_TOO_LOW" for f in row["findings"])


def test_worker_market_ready_candidate_warning(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "worker_mrc")
    _write_docs(temp_repo_root, ["worker_mrc"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "worker_mrc",
                app,
                productization_stage="market_ready_candidate",
                **{"class": "worker"},
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "worker_mrc")
    assert any(f["code"] == "STAGE_CLASS_CONFLICT" for f in row["findings"])
    assert row["level"] == "WARNING"


def test_internal_infra_market_ready_candidate_warning(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "infra_mrc")
    _write_docs(temp_repo_root, ["infra_mrc"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "infra_mrc",
                app,
                productization_stage="market_ready_candidate",
                **{"class": "internal_infra"},
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "infra_mrc")
    assert any(f["code"] == "STAGE_CLASS_CONFLICT" for f in row["findings"])


def test_readme_registry_drift_signal(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "drift_app", readme_text="# drift\ninternal helper only\n")
    _write_docs(temp_repo_root, ["drift_app"])
    _write_registry(temp_repo_root, [_base_entry("drift_app", app, primary_role="customer acquisition engine")])

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "drift_app")
    assert any(f["code"] == "PRIMARY_ROLE_README_MISMATCH" for f in row["findings"])


def test_reclassification_metadata_missing_signal(temp_repo_root: Path) -> None:
    app = _create_valid_app(temp_repo_root, "reclass_meta")
    _write_docs(temp_repo_root, ["reclass_meta"])
    _write_registry(
        temp_repo_root,
        [
            _base_entry(
                "reclass_meta",
                app,
                reclassification_history=[{"from": "internal_infra", "to": "worker", "at": "2026-03-08T00:00:00+00:00", "by": "human"}],
                reclassification_reason=None,
                **{"class": "worker"},
            )
        ],
    )

    report = run_check(temp_repo_root)
    row = next(item for item in report["checks"] if item["app"] == "reclass_meta")
    assert any(f["code"] == "RECLASS_REASON_MISSING" for f in row["findings"])


def test_json_report_has_stable_findings_schema(temp_repo_root: Path, capsys) -> None:
    app = _create_valid_app(temp_repo_root, "schema_app")
    _write_docs(temp_repo_root, ["schema_app"])
    entry = _base_entry("schema_app", app)
    entry.pop("class")
    _write_registry(temp_repo_root, [entry])

    old_cwd = Path.cwd()
    try:
        os.chdir(temp_repo_root)
        out_file = temp_repo_root / "artifacts" / "governance_check.json"
        exit_code = cli.main(["check", "--json-out", str(out_file)])
    finally:
        os.chdir(old_cwd)

    _ = capsys.readouterr().out
    assert exit_code == 0
    payload = json.loads(out_file.read_text(encoding="utf8"))
    assert payload["rule_order"] == [
        "required_structure",
        "naming",
        "registry_consistency",
        "governance_status",
        "classification_policy",
        "promotion_guard",
        "cross_surface_alignment",
        "documentation_alignment",
    ]
    item = next(row for row in payload["checks"] if row["app"] == "schema_app")
    assert "findings" in item
    assert all({"app", "code", "message", "severity", "rule"}.issubset(f.keys()) for f in item["findings"])
