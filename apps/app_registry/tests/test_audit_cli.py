from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from app_registry.cli import main as registry_cli_main
from app_registry import registry as registry_module


def _sandbox() -> Path:
    root = Path(__file__).resolve().parent / ".tmp" / f"audit_{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_audit_happy_path_ok(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app1 = sandbox / "apps" / "app_one"
        app2 = sandbox / "apps" / "app_two"
        app1.mkdir(parents=True)
        app2.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "app_one",
                            "version": "0.1.0",
                            "role": "worker",
                            "entrypoint": "app_one.cli:main",
                            "status": "active",
                            "score": 6,
                            "verified": True,
                            "app_path": str(app1),
                        },
                        {
                            "name": "app_two",
                            "version": "0.1.0",
                            "role": "worker",
                            "entrypoint": "app_two.cli:main",
                            "status": "candidate",
                            "score": 1,
                            "verified": True,
                            "app_path": str(app2),
                        },
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 0
        assert "registry audit:" in out
        assert "- app_one: OK" in out
        assert "- app_two: OK" in out
        assert "summary: total=2 ok=2 warning=0 error=0" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_missing_app_path_error(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "broken_app",
                            "entrypoint": "broken_app.cli:main",
                            "status": "active",
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 1
        assert "- broken_app: ERROR (app_path missing" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_path_not_found_error(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "ghost_app",
                            "entrypoint": "ghost_app.cli:main",
                            "status": "quarantine",
                            "app_path": str(sandbox / "missing_dir"),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 1
        assert "- ghost_app: ERROR (path not found" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_missing_entrypoint_error(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app_dir = sandbox / "apps" / "no_entry"
        app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "no_entry",
                            "status": "active",
                            "app_path": str(app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 1
        assert "- no_entry: ERROR (entrypoint missing" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_node_app_missing_entrypoint_warning(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app_dir = sandbox / "apps" / "node_dash"
        app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "node_dash",
                            "app_type": "node_app",
                            "layout": "custom",
                            "stack": "electron-vite",
                            "status": "candidate",
                            "score": 1,
                            "verified": False,
                            "app_path": str(app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- node_dash: WARNING (entrypoint missing (optional for node_app))" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_candidate_missing_score_is_ok(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app_dir = sandbox / "apps" / "candidate_no_score"
        app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "candidate_no_score",
                            "entrypoint": "candidate_no_score.cli:main",
                            "status": "candidate",
                            "score": None,
                            "verified": False,
                            "app_path": str(app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- candidate_no_score: OK" in out
        assert "missing score" not in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_active_missing_score_is_warning(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app_dir = sandbox / "apps" / "active_no_score"
        app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "active_no_score",
                            "entrypoint": "active_no_score.cli:main",
                            "status": "active",
                            "score": None,
                            "verified": False,
                            "app_path": str(app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- active_no_score: WARNING (" in out
        assert "missing score" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_missing_metadata_warning_only(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app_dir = sandbox / "apps" / "meta_app"
        app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "meta_app",
                            "entrypoint": "meta_app.cli:main",
                            "app_path": str(app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- meta_app: WARNING (" in out
        assert "missing status" in out
        assert "missing score" in out
        assert "missing verified" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_audit_backward_compatible_old_record(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        app_dir = sandbox / "apps" / "legacy"
        app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "legacy",
                            "version": "0.1.0",
                            "role": "legacy",
                            "entrypoint": "legacy.cli:main",
                            "app_path": str(app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        code = registry_cli_main(["audit"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- legacy: WARNING (" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)
