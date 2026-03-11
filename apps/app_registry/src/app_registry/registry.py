from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = APP_ROOT / "data" / "registry.json"
ALLOWED_STATUS = {"candidate", "active", "quarantine", "retired"}
VALID_CLASSES = {"worker", "internal_infra", "dual_role_product"}
VALID_EXTERNAL_PRODUCT_POTENTIAL = {"low", "medium", "high"}
VALID_PRODUCTIZATION_STAGE = {
    "experimental_lab",
    "internal_mvp",
    "internal_operational",
    "product_exploration",
    "product_candidate",
    "market_ready_candidate",
}


def _default_registry() -> dict:
    return {"apps": []}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_registry() -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        save_registry(_default_registry())


def load_registry() -> dict:
    ensure_registry()
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"registry file is invalid JSON: {REGISTRY_PATH}") from exc


def save_registry(data: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf8",
    )


def _normalize_app(app: dict) -> dict:
    normalized = dict(app)
    normalized.setdefault("app_type", "python_app")
    normalized.setdefault("layout", "src")
    normalized.setdefault("stack", None)
    normalized.setdefault("python_package", None)
    normalized.setdefault("status", None)
    normalized.setdefault("score", None)
    normalized.setdefault("verified", False)
    normalized.setdefault("source_template", None)
    normalized.setdefault("created_by", None)
    normalized.setdefault("app_path", None)
    normalized.setdefault("class", None)
    normalized.setdefault("primary_role", None)
    normalized.setdefault("internal_customer", None)
    normalized.setdefault("external_product_potential", None)
    normalized.setdefault("productization_stage", None)
    normalized.setdefault("class_assigned_at", None)
    normalized.setdefault("class_assigned_by", None)
    normalized.setdefault("reclassification_reason", None)
    normalized.setdefault("reclassification_history", [])
    return normalized


def _validate_enum(value: Any, allowed: set[str], field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"invalid {field_name}: {value!r} (allowed: {allowed_text})")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _normalize_internal_customer(value: Any) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("internal_customer must not be empty")
        return text
    if isinstance(value, list):
        if not value:
            raise ValueError("internal_customer list must not be empty")
        normalized_list: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("internal_customer list must contain non-empty strings")
            normalized_list.append(item.strip())
        return normalized_list
    raise ValueError("internal_customer must be a string or list[str]")


def _normalize_history(value: Any) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("reclassification_history must be a list")
    history: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            history.append(dict(item))
        else:
            raise ValueError("reclassification_history entries must be objects")
    return history


def _apply_classification_validation(updates: dict) -> dict:
    normalized = dict(updates)
    _validate_enum(normalized.get("class"), VALID_CLASSES, "class")
    _validate_non_empty_string(normalized.get("primary_role"), "primary_role")
    _validate_enum(
        normalized.get("external_product_potential"),
        VALID_EXTERNAL_PRODUCT_POTENTIAL,
        "external_product_potential",
    )
    _validate_enum(
        normalized.get("productization_stage"),
        VALID_PRODUCTIZATION_STAGE,
        "productization_stage",
    )
    if "internal_customer" in normalized:
        normalized["internal_customer"] = _normalize_internal_customer(normalized.get("internal_customer"))
    if "reclassification_history" in normalized:
        normalized["reclassification_history"] = _normalize_history(
            normalized.get("reclassification_history")
        )
    return normalized


def list_apps(status: str | None = None) -> list[dict]:
    data = load_registry()
    apps = [_normalize_app(app) for app in list(data.get("apps", []))]
    if status is None:
        return apps
    return [app for app in apps if app.get("status") == status]


def get_app(name: str) -> dict | None:
    for app in list_apps():
        if app.get("name") == name:
            return app
    return None


def add_app(
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
    data = load_registry()
    apps = [_normalize_app(app) for app in list(data.get("apps", []))]

    if any(app.get("name") == name for app in apps):
        raise ValueError(f"app already exists: {name}")

    app_payload = _apply_classification_validation(
        {
        "name": name,
        "version": version,
        "role": role,
        "entrypoint": entrypoint,
        "status": status,
        "score": score,
        "verified": bool(verified),
        "source_template": source_template,
        "created_by": created_by,
        "app_path": app_path,
        "class": class_name,
        "primary_role": primary_role,
        "internal_customer": internal_customer,
        "external_product_potential": external_product_potential,
        "productization_stage": productization_stage,
        "class_assigned_at": class_assigned_at,
        "class_assigned_by": class_assigned_by,
        "reclassification_reason": reclassification_reason,
        "reclassification_history": reclassification_history,
        "last_verified_at": _now_iso(),
        }
    )
    if app_payload.get("class") and not app_payload.get("class_assigned_at"):
        app_payload["class_assigned_at"] = _now_iso()
    if app_payload.get("class") and not app_payload.get("class_assigned_by"):
        app_payload["class_assigned_by"] = app_payload.get("created_by") or "human"
    app = _normalize_app(app_payload)
    apps.append(app)
    data["apps"] = apps
    save_registry(data)
    return app


def update_app(name: str, **updates: object) -> dict:
    data = load_registry()
    apps = [_normalize_app(app) for app in list(data.get("apps", []))]

    for i, app in enumerate(apps):
        if app.get("name") == name:
            normalized_updates = _apply_classification_validation(dict(updates))
            merged = dict(app)
            class_changed = (
                "class" in normalized_updates
                and normalized_updates.get("class") is not None
                and normalized_updates.get("class") != app.get("class")
            )

            merged.update(normalized_updates)
            merged["last_verified_at"] = _now_iso()
            if class_changed:
                history = _normalize_history(merged.get("reclassification_history"))
                history.append(
                    {
                        "from": app.get("class"),
                        "to": normalized_updates.get("class"),
                        "at": merged.get("class_assigned_at") or _now_iso(),
                        "by": normalized_updates.get("class_assigned_by") or app.get("class_assigned_by"),
                        "reason": normalized_updates.get("reclassification_reason"),
                    }
                )
                merged["reclassification_history"] = history
            merged = _normalize_app(merged)
            apps[i] = merged
            data["apps"] = apps
            save_registry(data)
            return merged

    raise ValueError(f"app not found: {name}")


def classify_app(
    name: str,
    class_name: str,
    primary_role: str,
    internal_customer: str | list[str],
    external_product_potential: str,
    productization_stage: str,
    assigned_by: str = "human",
    reason: str | None = None,
) -> dict:
    existing = get_app(name)
    if existing is None:
        raise ValueError(f"app not found: {name}")
    return update_app(
        name,
        **{
            "class": class_name,
            "primary_role": primary_role,
            "internal_customer": internal_customer,
            "external_product_potential": external_product_potential,
            "productization_stage": productization_stage,
            "class_assigned_at": _now_iso(),
            "class_assigned_by": assigned_by,
            "reclassification_reason": reason,
        },
    )


def build_audit_report() -> dict:
    data = load_registry()
    raw_apps = list(data.get("apps", []))
    items: list[dict] = []

    for raw in raw_apps:
        name = raw.get("name")
        display_name = str(name) if isinstance(name, str) and name.strip() else "<missing-name>"
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(name, str) or not name.strip():
            errors.append("name missing")

        app_path = raw.get("app_path")
        if not isinstance(app_path, str) or not app_path.strip():
            errors.append("app_path missing")
        elif not Path(app_path).exists():
            errors.append("path not found")

        app_type = raw.get("app_type")
        if not isinstance(app_type, str) or not app_type.strip():
            app_type = "python_app"

        entrypoint = raw.get("entrypoint")
        if not isinstance(entrypoint, str) or not entrypoint.strip():
            if app_type == "node_app":
                warnings.append("entrypoint missing (optional for node_app)")
            else:
                errors.append("entrypoint missing")

        status = raw.get("status")
        status_missing = "status" not in raw or status in (None, "")
        status_unknown = isinstance(status, str) and status not in ALLOWED_STATUS

        if status_missing:
            warnings.append("missing status")
        score_missing = "score" not in raw or raw.get("score") is None
        if score_missing and (status_missing or status_unknown or status == "active"):
            warnings.append("missing score")
        if "verified" not in raw:
            warnings.append("missing verified")

        if errors:
            level = "error"
            reason = ", ".join(errors)
        elif warnings:
            level = "warning"
            reason = ", ".join(warnings)
        else:
            level = "ok"
            reason = ""

        items.append(
            {
                "name": display_name,
                "level": level,
                "reason": reason,
                "status": raw.get("status"),
                "score": raw.get("score"),
                "verified": raw.get("verified"),
            }
        )

    summary = {
        "total": len(items),
        "ok": sum(1 for item in items if item["level"] == "ok"),
        "warning": sum(1 for item in items if item["level"] == "warning"),
        "error": sum(1 for item in items if item["level"] == "error"),
    }
    return {"items": items, "summary": summary}
