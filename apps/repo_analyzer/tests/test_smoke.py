from __future__ import annotations

import importlib
from pathlib import Path

from repo_analyzer.core import check_apps


def test_cli_module_imports() -> None:
    module = importlib.import_module("repo_analyzer.cli")
    assert hasattr(module, "main")


def test_check_function_returns_list() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    results = check_apps(repo_root)
    assert isinstance(results, list)