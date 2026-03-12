from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from app_registry.core import add_record, classify_record, list_records, show_record
from app_registry.cli import main as registry_cli_main
from app_registry import registry as registry_module


def test_add_record_accepts_extended_fields() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        created = add_record(
            name="ops_guard",
            version="0.1.0",
            role="Ops guard app",
            entrypoint="ops_guard.cli:main",
            status="active",
            score=7,
            verified=True,
            source_template="wrg_app",
            created_by="devtool_factory",
            app_path=r"C:\dev\WinstonRedGuard\apps\ops_guard",
        )
        assert created["status"] == "active"
        assert created["score"] == 7
        assert created["verified"] is True
        assert created["source_template"] == "wrg_app"
        assert created["created_by"] == "devtool_factory"
        assert created["app_path"] == r"C:\dev\WinstonRedGuard\apps\ops_guard"
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_old_records_are_readable_with_defaults() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "legacy_app",
                            "version": "0.1.0",
                            "role": "legacy",
                            "entrypoint": "legacy_app.cli:main",
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        listed = list_records()
        shown = show_record("legacy_app")
        assert listed[0]["name"] == "legacy_app"
        assert shown["status"] is None
        assert shown["score"] is None
        assert shown["verified"] is False
        assert shown["source_template"] is None
        assert shown["created_by"] is None
        assert shown["app_path"] is None
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_add_record_duplicate_still_fails() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        add_record(
            name="dup_app",
            version="0.1.0",
            role="dup",
            entrypoint="dup_app.cli:main",
        )
        try:
            add_record(
                name="dup_app",
                version="0.1.0",
                role="dup",
                entrypoint="dup_app.cli:main",
            )
            raise AssertionError("expected duplicate add to fail")
        except ValueError as exc:
            assert "already exists" in str(exc)
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def _create_fake_evaluator_src(root: Path, score: int, ok: bool) -> Path:
    src_root = root / "fake_app_evaluator_src"
    pkg_dir = src_root / "app_evaluator"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf8")
    (pkg_dir / "core.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_evaluation(app_path: str, json_out: str | None = None) -> dict:",
                "    return {",
                f"        'score': {score},",
                f"        'ok': {str(ok)},",
                "        'app_path': app_path,",
                "    }",
            ]
        )
        + "\n",
        encoding="utf8",
    )
    return src_root


def test_list_with_status_filter_quarantine_only() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        add_record(
            name="active_app",
            version="0.1.0",
            role="active",
            entrypoint="active_app.cli:main",
            status="active",
        )
        add_record(
            name="q_app",
            version="0.1.0",
            role="quarantine",
            entrypoint="q_app.cli:main",
            status="quarantine",
        )
        filtered = list_records(status="quarantine")
        assert [app["name"] for app in filtered] == ["q_app"]
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_pass_activates_app() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    original_eval_src = os.environ.get("APP_EVALUATOR_SRC")
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        fake_eval_src = _create_fake_evaluator_src(sandbox, score=6, ok=True)
        os.environ["APP_EVALUATOR_SRC"] = str(fake_eval_src)

        add_record(
            name="saha_guard",
            version="0.1.0",
            role="quarantine test",
            entrypoint="saha_guard.cli:main",
            status="quarantine",
            app_path=str(sandbox / "apps" / "saha_guard"),
        )
        code = registry_cli_main(["reevaluate", "saha_guard", "--min-score", "5"])
        assert code == 0
        shown = show_record("saha_guard")
        assert shown["status"] == "active"
        assert shown["score"] == 6
        assert shown["verified"] is True
    finally:
        if original_eval_src is None:
            os.environ.pop("APP_EVALUATOR_SRC", None)
        else:
            os.environ["APP_EVALUATOR_SRC"] = original_eval_src
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_fail_keeps_quarantine_and_updates_score() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    original_eval_src = os.environ.get("APP_EVALUATOR_SRC")
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        fake_eval_src = _create_fake_evaluator_src(sandbox, score=4, ok=True)
        os.environ["APP_EVALUATOR_SRC"] = str(fake_eval_src)

        add_record(
            name="saha_guard",
            version="0.1.0",
            role="quarantine test",
            entrypoint="saha_guard.cli:main",
            status="quarantine",
            app_path=str(sandbox / "apps" / "saha_guard"),
        )
        code = registry_cli_main(["reevaluate", "saha_guard", "--min-score", "5"])
        assert code == 0
        shown = show_record("saha_guard")
        assert shown["status"] == "quarantine"
        assert shown["score"] == 4
        assert shown["verified"] is False
    finally:
        if original_eval_src is None:
            os.environ.pop("APP_EVALUATOR_SRC", None)
        else:
            os.environ["APP_EVALUATOR_SRC"] = original_eval_src
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_not_found_returns_error() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        code = registry_cli_main(["reevaluate", "missing_app", "--min-score", "5"])
        assert code == 1
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_missing_app_path_returns_error() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        add_record(
            name="saha_guard",
            version="0.1.0",
            role="missing path",
            entrypoint="saha_guard.cli:main",
            status="quarantine",
            app_path=None,
        )
        code = registry_cli_main(["reevaluate", "saha_guard", "--min-score", "5"])
        assert code == 1
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_active_can_drop_to_quarantine() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    original_eval_src = os.environ.get("APP_EVALUATOR_SRC")
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        fake_eval_src = _create_fake_evaluator_src(sandbox, score=2, ok=True)
        os.environ["APP_EVALUATOR_SRC"] = str(fake_eval_src)

        add_record(
            name="active_app",
            version="0.1.0",
            role="active",
            entrypoint="active_app.cli:main",
            status="active",
            app_path=str(sandbox / "apps" / "active_app"),
        )
        code = registry_cli_main(
            ["reevaluate", "active_app", "--min-score", "5", "--activate-on-pass"]
        )
        assert code == 0
        shown = show_record("active_app")
        assert shown["status"] == "quarantine"
        assert shown["score"] == 2
    finally:
        if original_eval_src is None:
            os.environ.pop("APP_EVALUATOR_SRC", None)
        else:
            os.environ["APP_EVALUATOR_SRC"] = original_eval_src
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_add_record_with_valid_classification_metadata() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        created = add_record(
            name="classed_app",
            version="0.1.0",
            role="worker",
            entrypoint="classed_app.cli:main",
            class_name="worker",
            primary_role="ops guard",
            internal_customer=["ops", "qa"],
            external_product_potential="medium",
            productization_stage="internal_mvp",
            class_assigned_by="human",
        )
        assert created["class"] == "worker"
        assert created["primary_role"] == "ops guard"
        assert created["internal_customer"] == ["ops", "qa"]
        assert created["external_product_potential"] == "medium"
        assert created["productization_stage"] == "internal_mvp"
        assert isinstance(created["class_assigned_at"], str)
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_invalid_class_is_rejected() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        try:
            add_record(
                name="bad_class",
                version="0.1.0",
                role="worker",
                entrypoint="bad_class.cli:main",
                class_name="unknown_class",
            )
            raise AssertionError("expected invalid class to fail")
        except ValueError as exc:
            assert "invalid class" in str(exc)
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_invalid_productization_stage_is_rejected() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        try:
            add_record(
                name="bad_stage",
                version="0.1.0",
                role="worker",
                entrypoint="bad_stage.cli:main",
                productization_stage="ga",
            )
            raise AssertionError("expected invalid stage to fail")
        except ValueError as exc:
            assert "invalid productization_stage" in str(exc)
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_classify_app_appends_reclassification_history() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        add_record(
            name="reclass_app",
            version="0.1.0",
            role="worker",
            entrypoint="reclass_app.cli:main",
            class_name="worker",
            primary_role="internal helper",
            internal_customer="ops",
            external_product_potential="low",
            productization_stage="internal_mvp",
            class_assigned_by="human",
        )
        updated = classify_record(
            name="reclass_app",
            class_name="dual_role_product",
            primary_role="dual utility tool",
            internal_customer=["ops", "external builders"],
            external_product_potential="high",
            productization_stage="product_candidate",
            assigned_by="governance_check",
            reason="validated productization track",
        )
        assert updated["class"] == "dual_role_product"
        assert updated["class_assigned_by"] == "governance_check"
        assert updated["reclassification_reason"] == "validated productization track"
        history = updated["reclassification_history"]
        assert isinstance(history, list)
        assert len(history) == 1
        assert history[0]["from"] == "worker"
        assert history[0]["to"] == "dual_role_product"
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_old_records_get_new_classification_defaults() -> None:
    sandbox = Path(__file__).resolve().parent / ".tmp" / f"registry_{uuid.uuid4().hex}"
    sandbox.mkdir(parents=True, exist_ok=False)
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "legacy_classless",
                            "version": "0.1.0",
                            "role": "legacy",
                            "entrypoint": "legacy_classless.cli:main",
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        shown = show_record("legacy_classless")
        assert shown["class"] is None
        assert shown["primary_role"] is None
        assert shown["internal_customer"] is None
        assert shown["external_product_potential"] is None
        assert shown["productization_stage"] is None
        assert shown["class_assigned_at"] is None
        assert shown["class_assigned_by"] is None
        assert shown["reclassification_reason"] is None
        assert shown["reclassification_history"] == []
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)
