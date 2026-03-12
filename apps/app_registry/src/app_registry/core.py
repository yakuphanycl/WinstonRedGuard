from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path

from .registry import add_app, build_audit_report, classify_app, get_app, list_apps, update_app


def list_records(status: str | None = None) -> list[dict]:
    return list_apps(status=status)


def show_record(name: str) -> dict:
    app = get_app(name)
    if app is None:
        raise ValueError(f"app not found: {name}")
    return app


def add_record(
    name: str,
    version: str,
    role: str,
    entrypoint: str,
    status: str = "active",
    score: int | None = None,
    verified: bool = False,
    source_template: str | None = None,
    created_by: str | None = None,
    app_path: str | None = None,
    class_name: str | None = None,
    primary_role: str | None = None,
    internal_customer: str | list[str] | None = None,
    external_product_potential: str | None = None,
    productization_stage: str | None = None,
    class_assigned_at: str | None = None,
    class_assigned_by: str | None = None,
    reclassification_reason: str | None = None,
    reclassification_history: list[dict] | None = None,
) -> dict:
    return add_app(
        name=name,
        version=version,
        role=role,
        entrypoint=entrypoint,
        status=status,
        score=score,
        verified=verified,
        source_template=source_template,
        created_by=created_by,
        app_path=app_path,
        class_name=class_name,
        primary_role=primary_role,
        internal_customer=internal_customer,
        external_product_potential=external_product_potential,
        productization_stage=productization_stage,
        class_assigned_at=class_assigned_at,
        class_assigned_by=class_assigned_by,
        reclassification_reason=reclassification_reason,
        reclassification_history=reclassification_history,
    )


def classify_record(
    name: str,
    class_name: str,
    primary_role: str,
    internal_customer: str | list[str],
    external_product_potential: str,
    productization_stage: str,
    assigned_by: str = "human",
    reason: str | None = None,
) -> dict:
    return classify_app(
        name=name,
        class_name=class_name,
        primary_role=primary_role,
        internal_customer=internal_customer,
        external_product_potential=external_product_potential,
        productization_stage=productization_stage,
        assigned_by=assigned_by,
        reason=reason,
    )


def _run_evaluation(app_path: str) -> dict:
    app_evaluator_src_override = os.environ.get("APP_EVALUATOR_SRC")
    if app_evaluator_src_override:
        app_evaluator_src = Path(app_evaluator_src_override)
    else:
        repo_root = Path(__file__).resolve().parents[4]
        app_evaluator_src = repo_root / "apps" / "app_evaluator" / "src"

    if str(app_evaluator_src) not in sys.path:
        sys.path.insert(0, str(app_evaluator_src))
    else:
        # ensure override path wins in repeated calls/tests
        sys.path.remove(str(app_evaluator_src))
        sys.path.insert(0, str(app_evaluator_src))

    if app_evaluator_src_override:
        sys.modules.pop("app_evaluator.core", None)
        sys.modules.pop("app_evaluator", None)

    evaluator_core = import_module("app_evaluator.core")
    return evaluator_core.run_evaluation(app_path=app_path)


def reevaluate_record(name: str, min_score: int = 0, activate_on_pass: bool = False) -> dict:
    app = show_record(name)
    app_path = app.get("app_path")
    if not isinstance(app_path, str) or not app_path.strip():
        raise ValueError(f"app_path missing for registry entry: {name}")

    report = _run_evaluation(app_path)
    score = int(report.get("score", 0))
    passed = bool(report.get("ok", False)) and score >= int(min_score)

    if passed:
        status = "active"
        updated = update_app(name, score=score, verified=True, status=status)
    else:
        updated = update_app(name, score=score, verified=False, status="quarantine")

    return {
        "name": name,
        "score": score,
        "min_score": int(min_score),
        "passed": passed,
        "status": updated.get("status"),
    }


def run_audit() -> dict:
    return build_audit_report()


def format_audit_report(report: dict) -> str:
    lines = ["registry audit:"]
    for item in report["items"]:
        level = str(item["level"]).upper()
        if item["reason"]:
            lines.append(f"- {item['name']}: {level} ({item['reason']})")
        else:
            lines.append(f"- {item['name']}: {level}")
    summary = report["summary"]
    lines.append(
        f"summary: total={summary['total']} ok={summary['ok']} "
        f"warning={summary['warning']} error={summary['error']}"
    )
    return "\n".join(lines)


def reevaluate_all_records(
    min_score: int,
    activate_on_pass: bool = False,
    status: str | None = None,
) -> dict:
    records = list_records()
    items: list[dict] = []

    for app in records:
        name = app.get("name")
        display_name = str(name) if isinstance(name, str) and name.strip() else "<missing-name>"

        if status is not None and app.get("status") != status:
            items.append(
                {
                    "name": display_name,
                    "level": "skipped",
                    "message": "status filter mismatch",
                }
            )
            continue

        if not isinstance(name, str) or not name.strip():
            items.append({"name": display_name, "level": "skipped", "message": "name missing"})
            continue

        app_path = app.get("app_path")
        if not isinstance(app_path, str) or not app_path.strip():
            items.append({"name": display_name, "level": "skipped", "message": "app_path missing"})
            continue

        app_path_obj = Path(app_path)
        if not app_path_obj.exists():
            items.append({"name": display_name, "level": "skipped", "message": "path not found"})
            continue

        try:
            report = _run_evaluation(app_path)
        except Exception as exc:
            items.append(
                {
                    "name": display_name,
                    "level": "error",
                    "message": f"evaluator error: {exc}",
                }
            )
            continue

        score = int(report.get("score", 0))
        passed = bool(report.get("ok", False)) and score >= int(min_score)
        next_status = "active" if passed else "quarantine"
        if passed and activate_on_pass:
            next_status = "active"

        try:
            update_app(name, score=score, verified=passed, status=next_status)
        except Exception as exc:
            items.append(
                {
                    "name": display_name,
                    "level": "error",
                    "message": f"registry update failed: {exc}",
                }
            )
            continue

        items.append(
            {
                "name": display_name,
                "level": "updated",
                "message": f"score={score}, status={next_status}",
            }
        )

    summary = {
        "total": len(items),
        "updated": sum(1 for item in items if item["level"] == "updated"),
        "skipped": sum(1 for item in items if item["level"] == "skipped"),
        "error": sum(1 for item in items if item["level"] == "error"),
    }
    return {"items": items, "summary": summary}


def format_reevaluate_all_report(report: dict) -> str:
    lines = ["registry reevaluate-all:"]
    for item in report["items"]:
        lines.append(f"- {item['name']}: {str(item['level']).upper()} ({item['message']})")
    summary = report["summary"]
    lines.append(
        f"summary: total={summary['total']} updated={summary['updated']} "
        f"skipped={summary['skipped']} error={summary['error']}"
    )
    return "\n".join(lines)
