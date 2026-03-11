from __future__ import annotations

import importlib


def test_import_cli_module() -> None:
    module = importlib.import_module("wrg_orchestrator.cli")
    assert hasattr(module, "main")

