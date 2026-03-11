from __future__ import annotations

from pathlib import Path

from .evaluator import evaluate_app, write_report


def run_evaluation(app_path: str, json_out: str | None = None) -> dict:
    report = evaluate_app(Path(app_path))
    if json_out:
        write_report(report, Path(json_out))
    return report
