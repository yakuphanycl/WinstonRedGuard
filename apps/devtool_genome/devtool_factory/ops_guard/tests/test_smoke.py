from __future__ import annotations

import importlib


def test_import_cli_module() -> None:
    module = importlib.import_module("ops_guard.cli")
    assert hasattr(module, "main")

