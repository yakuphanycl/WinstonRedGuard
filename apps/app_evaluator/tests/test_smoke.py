import importlib


def test_cli_exists():
    mod = importlib.import_module("app_evaluator.cli")
    assert hasattr(mod, "main")
