from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from app_registry.cli import main as registry_cli_main
from app_registry.core import add_record, show_record
from app_registry import registry as registry_module


def _sandbox() -> Path:
    root = Path(__file__).resolve().parent / ".tmp" / f"reeval_all_{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_reevaluate_all_happy_path(monkeypatch, capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        app1 = sandbox / "apps" / "a1"
        app2 = sandbox / "apps" / "a2"
        app1.mkdir(parents=True)
        app2.mkdir(parents=True)
        add_record("a1", "0.1.0", "r1", "a1.cli:main", status="quarantine", app_path=str(app1))
        add_record("a2", "0.1.0", "r2", "a2.cli:main", status="candidate", app_path=str(app2))

        monkeypatch.setattr("app_registry.core._run_evaluation", lambda _p: {"ok": True, "score": 6})
        code = registry_cli_main(["reevaluate-all", "--min-score", "4"])
        out = capsys.readouterr().out

        assert code == 0
        assert "registry reevaluate-all:" in out
        assert "- a1: UPDATED (score=6, status=active)" in out
        assert "- a2: UPDATED (score=6, status=active)" in out
        assert "summary: total=2 updated=2 skipped=0 error=0" in out
        assert show_record("a1")["status"] == "active"
        assert show_record("a2")["status"] == "active"
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_all_one_pass_one_fail(monkeypatch, capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        app1 = sandbox / "apps" / "a1"
        app2 = sandbox / "apps" / "a2"
        app1.mkdir(parents=True)
        app2.mkdir(parents=True)
        add_record("a1", "0.1.0", "r1", "a1.cli:main", status="quarantine", app_path=str(app1))
        add_record("a2", "0.1.0", "r2", "a2.cli:main", status="active", app_path=str(app2))

        def fake_eval(p: str) -> dict:
            if p.endswith("a1"):
                return {"ok": True, "score": 7}
            return {"ok": True, "score": 2}

        monkeypatch.setattr("app_registry.core._run_evaluation", fake_eval)
        code = registry_cli_main(["reevaluate-all", "--min-score", "4"])
        out = capsys.readouterr().out

        assert code == 0
        assert "- a1: UPDATED (score=7, status=active)" in out
        assert "- a2: UPDATED (score=2, status=quarantine)" in out
        assert show_record("a1")["status"] == "active"
        assert show_record("a2")["status"] == "quarantine"
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_all_missing_app_path_skipped(monkeypatch, capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        add_record("a1", "0.1.0", "r1", "a1.cli:main", status="quarantine", app_path=None)
        called = {"count": 0}

        def fake_eval(_p: str) -> dict:
            called["count"] += 1
            return {"ok": True, "score": 9}

        monkeypatch.setattr("app_registry.core._run_evaluation", fake_eval)
        code = registry_cli_main(["reevaluate-all", "--min-score", "4"])
        out = capsys.readouterr().out

        assert code == 0
        assert "- a1: SKIPPED (app_path missing)" in out
        assert called["count"] == 0
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_all_path_not_found_skipped(capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        add_record(
            "ghost",
            "0.1.0",
            "ghost",
            "ghost.cli:main",
            status="quarantine",
            app_path=str(sandbox / "apps" / "ghost"),
        )
        code = registry_cli_main(["reevaluate-all", "--min-score", "4"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- ghost: SKIPPED (path not found)" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_all_status_filter(monkeypatch, capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        q = sandbox / "apps" / "q"
        a = sandbox / "apps" / "a"
        q.mkdir(parents=True)
        a.mkdir(parents=True)
        add_record("q", "0.1.0", "r", "q.cli:main", status="quarantine", app_path=str(q))
        add_record("a", "0.1.0", "r", "a.cli:main", status="active", app_path=str(a))
        monkeypatch.setattr("app_registry.core._run_evaluation", lambda _p: {"ok": True, "score": 5})

        code = registry_cli_main(["reevaluate-all", "--min-score", "4", "--status", "quarantine"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- q: UPDATED (score=5, status=active)" in out
        assert "- a: SKIPPED (status filter mismatch)" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_all_evaluator_exception_counts_error(monkeypatch, capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        app1 = sandbox / "apps" / "ok"
        app2 = sandbox / "apps" / "bad"
        app1.mkdir(parents=True)
        app2.mkdir(parents=True)
        add_record("ok", "0.1.0", "r", "ok.cli:main", status="quarantine", app_path=str(app1))
        add_record("bad", "0.1.0", "r", "bad.cli:main", status="quarantine", app_path=str(app2))

        def fake_eval(p: str) -> dict:
            if p.endswith("bad"):
                raise RuntimeError("boom")
            return {"ok": True, "score": 8}

        monkeypatch.setattr("app_registry.core._run_evaluation", fake_eval)
        code = registry_cli_main(["reevaluate-all", "--min-score", "4"])
        out = capsys.readouterr().out
        assert code == 1
        assert "- ok: UPDATED (score=8, status=active)" in out
        assert "- bad: ERROR (evaluator error: boom)" in out
        assert "error=1" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)


def test_reevaluate_all_backward_compatible_old_entry(monkeypatch, capsys) -> None:
    sandbox = _sandbox()
    original_path = registry_module.REGISTRY_PATH
    try:
        registry_module.REGISTRY_PATH = sandbox / "registry.json"
        old_app_dir = sandbox / "apps" / "legacy"
        old_app_dir.mkdir(parents=True)
        registry_module.REGISTRY_PATH.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "legacy",
                            "version": "0.1.0",
                            "role": "legacy",
                            "entrypoint": "legacy.cli:main",
                            "app_path": str(old_app_dir),
                        }
                    ]
                }
            ),
            encoding="utf8",
        )
        monkeypatch.setattr("app_registry.core._run_evaluation", lambda _p: {"ok": True, "score": 5})
        code = registry_cli_main(["reevaluate-all", "--min-score", "4"])
        out = capsys.readouterr().out
        assert code == 0
        assert "- legacy: UPDATED (score=5, status=active)" in out
    finally:
        registry_module.REGISTRY_PATH = original_path
        shutil.rmtree(sandbox, ignore_errors=True)
