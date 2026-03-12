from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

RULE_ORDER = [
    "required_structure",
    "naming",
    "registry_consistency",
    "governance_status",
    "classification_policy",
    "promotion_guard",
    "cross_surface_alignment",
    "documentation_alignment",
]

VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DOCS_TOKEN_BLACKLIST = {
    "class",
    "worker",
    "primary_role",
    "productization_stage",
    "internal_customer",
    "external_product_potential",
    "internal_infra",
    "dual_role_product",
}
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
DUAL_ROLE_MIN_STAGES = {"product_candidate", "market_ready_candidate"}


def _find_doc_pair(repo_root: Path) -> tuple[Path | None, Path | None]:
    direct_company = repo_root / "company_map.md"
    direct_agent = repo_root / "AGENT_CONTEXT.md"
    if direct_company.exists() and direct_agent.exists():
        return direct_company, direct_agent

    return None, None


def _load_documented_workers(repo_root: Path) -> set[str]:
    company_path, agent_path = _find_doc_pair(repo_root)
    workers: set[str] = set()
    for path in (company_path, agent_path):
        if path is None:
            continue
        text = path.read_text(encoding="utf8")
        for match in re.findall(r"`([a-z][a-z0-9_]*)`", text):
            if not VALID_NAME_RE.match(match):
                continue
            if match in DOCS_TOKEN_BLACKLIST:
                continue
            workers.add(match)
    return workers


def _registry_path(repo_root: Path) -> Path:
    return repo_root / "apps" / "app_registry" / "data" / "registry.json"


def _load_registry_entries(repo_root: Path) -> list[dict]:
    registry_path = _registry_path(repo_root)
    if not registry_path.exists():
        return []
    try:
        data = json.loads(registry_path.read_text(encoding="utf8"))
    except json.JSONDecodeError:
        return []
    apps = data.get("apps", [])
    return [app for app in apps if isinstance(app, dict)]


def _app_dirs(repo_root: Path) -> list[Path]:
    apps_root = repo_root / "apps"
    if not apps_root.exists():
        return []
    return sorted([p for p in apps_root.iterdir() if p.is_dir()], key=lambda p: p.name)


def _entrypoint_exists(entry: dict) -> bool:
    entrypoint = entry.get("entrypoint")
    return isinstance(entrypoint, str) and bool(entrypoint.strip())


def _registry_app_type(app_dir: Path | None, registry_entry: dict | None) -> str:
    if registry_entry is not None:
        value = registry_entry.get("app_type")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if app_dir is not None and (app_dir / "package.json").exists() and not (app_dir / "pyproject.toml").exists():
        return "node_app"
    return "python_app"


def _registry_layout(registry_entry: dict | None, app_type: str) -> str:
    if registry_entry is not None:
        value = registry_entry.get("layout")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if app_type == "node_app":
        return "custom"
    return "src"


def _registry_python_package(app_name: str, registry_entry: dict | None) -> str:
    if registry_entry is not None:
        value = registry_entry.get("python_package")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return app_name


def _package_path(app_dir: Path, layout: str, package_name: str) -> Path:
    if layout == "src":
        return app_dir / "src" / package_name
    return app_dir / package_name


def _cli_candidates(app_dir: Path, layout: str, package_name: str) -> list[Path]:
    src_pkg = app_dir / "src" / package_name
    flat_pkg = app_dir / package_name
    if layout == "src":
        return [src_pkg / "cli.py", src_pkg / "cli" / "main.py"]
    if layout == "flat":
        return [flat_pkg / "cli.py", flat_pkg / "cli" / "main.py"]
    return [
        src_pkg / "cli.py",
        src_pkg / "cli" / "main.py",
        flat_pkg / "cli.py",
        flat_pkg / "cli" / "main.py",
    ]


def _has_project_scripts(app_dir: Path) -> bool:
    pyproject_path = app_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return False
    text = pyproject_path.read_text(encoding="utf8", errors="ignore")
    if tomllib is not None:
        try:
            parsed = tomllib.loads(text)
            project = parsed.get("project")
            scripts = project.get("scripts") if isinstance(project, dict) else None
            return isinstance(scripts, dict) and any(
                isinstance(key, str) and key.strip() and isinstance(value, str) and value.strip()
                for key, value in scripts.items()
            )
        except Exception:
            pass

    in_scripts = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_scripts = line == "[project.scripts]"
            continue
        if in_scripts and "=" in line:
            left, right = line.split("=", 1)
            if left.strip() and right.strip():
                return True
    return False


def _contains_json_signal(app_dir: Path, app_name: str, package_name: str, layout: str) -> bool:
    candidates = [app_dir / "README.md"]
    roots: list[Path]
    if layout == "src":
        roots = [app_dir / "src" / package_name]
    elif layout == "flat":
        roots = [app_dir / package_name]
    else:
        roots = [app_dir / "src" / package_name, app_dir / package_name, app_dir / "src" / app_name]
    for root in roots:
        if root.exists():
            candidates.extend(sorted(root.rglob("*.py")))
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf8", errors="ignore").lower()
        if "--json-out" in text or "json" in text:
            return True
    return False


def _readme_text(app_dir: Path) -> str:
    readme = app_dir / "README.md"
    if not readme.exists() or not readme.is_file():
        return ""
    return readme.read_text(encoding="utf8", errors="ignore").lower()


def _has_product_signal(readme_text: str) -> bool:
    if not readme_text.strip():
        return False
    keywords = ("product", "customer", "market", "pricing", "external")
    return len(readme_text) >= 80 and any(keyword in readme_text for keyword in keywords)


def _primary_role_aligned(primary_role: str, readme_text: str) -> bool:
    role_tokens = [token for token in re.split(r"[^a-z0-9]+", primary_role.lower()) if len(token) >= 4]
    if not role_tokens:
        return True
    return any(token in readme_text for token in role_tokens)


def _suggestion_for_code(code: str) -> str:
    mapping = {
        "MISSING_README": "add README.md",
        "MISSING_PACKAGE_JSON": "add package.json for node app",
        "MISSING_PYPROJECT": "add pyproject.toml",
        "MISSING_SRC_PACKAGE": "create package path for declared layout",
        "MISSING_TESTS": "add tests/ with at least one test_*.py",
        "MISSING_CLI_AND_ENTRYPOINT": "add CLI module/project.scripts or set registry entrypoint",
        "INVALID_APP_NAME": "rename app folder to snake_case python identifier",
        "UNREGISTERED_APP": "register worker or remove unmanaged app",
        "REGISTRY_APP_PATH_MISSING": "set app_path in app_registry",
        "REGISTRY_APP_PATH_NOT_FOUND": "fix app_path or remove stale registry entry",
        "REGISTRY_NAME_PATH_MISMATCH": "align registry name with app_path folder",
        "UNKNOWN_STATUS": "use one of: candidate, active, quarantine, retired",
        "ACTIVE_NOT_VERIFIED": "set verified=true after successful evaluation",
        "DOCS_MISSING_APP": "update company_map.md / AGENT_CONTEXT.md or register intended exception",
        "DOCS_WORKER_NOT_FOUND": "create documented worker or update governance docs",
        "CLASS_MISSING": "set class in registry metadata",
        "CLASS_INVALID": "use class: worker | internal_infra | dual_role_product",
        "PRIMARY_ROLE_MISSING": "set primary_role in registry metadata",
        "INTERNAL_CUSTOMER_MISSING": "set internal_customer in registry metadata",
        "INTERNAL_CUSTOMER_INVALID": "use internal_customer as non-empty string or list of strings",
        "EXTERNAL_PRODUCT_POTENTIAL_MISSING": "set external_product_potential: low|medium|high",
        "EXTERNAL_PRODUCT_POTENTIAL_INVALID": "fix external_product_potential enum value",
        "PRODUCTIZATION_STAGE_MISSING": "set productization_stage enum value",
        "PRODUCTIZATION_STAGE_INVALID": "fix productization_stage enum value",
        "BIRTH_CLASS_RULE_VIOLATION": "promote to dual_role_product through explicit reclassification trail",
        "RECLASS_ASSIGNED_BY_MISSING": "set class_assigned_by",
        "RECLASS_ASSIGNED_AT_MISSING": "set class_assigned_at",
        "RECLASS_REASON_MISSING": "set reclassification_reason",
        "RECLASS_HISTORY_INVALID": "store reclassification_history as a list of transition objects",
        "DUAL_ROLE_TESTS_REQUIRED": "add tests before dual_role_product classification",
        "DUAL_ROLE_CLI_REQUIRED": "add CLI entrypoint before dual_role_product classification",
        "DUAL_ROLE_JSON_REQUIRED": "add machine-readable JSON output contract",
        "DUAL_ROLE_README_SIGNAL_WEAK": "document product intent and customer/market context in README",
        "DUAL_ROLE_STAGE_TOO_LOW": "set productization_stage to product_candidate or market_ready_candidate",
        "STAGE_CLASS_CONFLICT": "align class and productization_stage policy",
        "PRIMARY_ROLE_README_MISMATCH": "align README role statement with primary_role metadata",
    }
    return mapping.get(code, "review governance policy and align metadata")


def _add_finding(
    findings: list[dict],
    app: str,
    code: str,
    message: str,
    severity: str,
    rule: str,
) -> None:
    findings.append(
        {
            "app": app,
            "code": code,
            "message": message,
            "severity": severity,
            "rule": rule,
        }
    )


def _build_issue_lists(findings: list[dict]) -> tuple[list[str], list[str]]:
    errors = [f["message"] for f in findings if f["severity"] == "ERROR"]
    warnings = [f["message"] for f in findings if f["severity"] == "WARNING"]
    return errors, warnings


def build_governance_report(repo_root: Path) -> dict:
    app_dirs = _app_dirs(repo_root)
    physical_apps = {p.name: p for p in app_dirs}

    registry_entries = _load_registry_entries(repo_root)
    registry_present = _registry_path(repo_root).exists()
    registry_by_name = {
        entry.get("name"): entry
        for entry in registry_entries
        if isinstance(entry.get("name"), str) and entry.get("name")
    }

    documented_workers = _load_documented_workers(repo_root)
    all_names = sorted(set(physical_apps.keys()) | set(registry_by_name.keys()) | set(documented_workers))

    checks: list[dict] = []
    for name in all_names:
        app_dir = physical_apps.get(name)
        registry_entry = registry_by_name.get(name)
        findings: list[dict] = []

        app_type = _registry_app_type(app_dir, registry_entry)
        layout = _registry_layout(registry_entry, app_type)
        python_package = _registry_python_package(name, registry_entry)
        readme_text = _readme_text(app_dir) if app_dir is not None else ""
        tests_present = bool(app_dir is not None and (app_dir / "tests").exists())
        has_entrypoint = registry_entry is not None and _entrypoint_exists(registry_entry)
        has_project_scripts = bool(app_dir is not None and _has_project_scripts(app_dir))
        cli_present = bool(
            app_dir is not None and any(path.exists() for path in _cli_candidates(app_dir, layout, python_package))
        )
        cli_signal_present = cli_present or has_entrypoint or has_project_scripts
        json_signal = bool(app_dir is not None and _contains_json_signal(app_dir, name, python_package, layout))

        # required_structure + naming
        if app_dir is not None:
            if not VALID_NAME_RE.match(name):
                _add_finding(findings, name, "INVALID_APP_NAME", "invalid app folder name", "ERROR", "naming")
            if not (app_dir / "README.md").exists():
                _add_finding(findings, name, "MISSING_README", "missing README.md", "WARNING", "required_structure")
            if app_type == "node_app":
                if not (app_dir / "package.json").exists():
                    _add_finding(
                        findings,
                        name,
                        "MISSING_PACKAGE_JSON",
                        "missing package.json",
                        "ERROR",
                        "required_structure",
                    )
            else:
                if not (app_dir / "pyproject.toml").exists():
                    severity = "WARNING" if layout in {"legacy_flat", "custom"} else "ERROR"
                    _add_finding(
                        findings,
                        name,
                        "MISSING_PYPROJECT",
                        "missing pyproject.toml",
                        severity,
                        "required_structure",
                    )
                if not _package_path(app_dir, layout, python_package).exists():
                    severity = "WARNING" if layout in {"legacy_flat", "custom"} else "ERROR"
                    _add_finding(
                        findings,
                        name,
                        "MISSING_SRC_PACKAGE",
                        "missing package path for declared layout",
                        severity,
                        "required_structure",
                    )
                if not cli_signal_present:
                    severity = "WARNING" if layout in {"legacy_flat", "custom"} else "ERROR"
                    _add_finding(
                        findings,
                        name,
                        "MISSING_CLI_AND_ENTRYPOINT",
                        "missing cli/module script signal and registry entrypoint",
                        severity,
                        "required_structure",
                    )
            if not tests_present:
                _add_finding(findings, name, "MISSING_TESTS", "missing tests", "WARNING", "required_structure")
            if registry_present and registry_entry is None:
                _add_finding(
                    findings,
                    name,
                    "UNREGISTERED_APP",
                    "app exists in apps/ but is not registered",
                    "ERROR",
                    "registry_consistency",
                )
            if documented_workers and name not in documented_workers:
                _add_finding(
                    findings,
                    name,
                    "DOCS_MISSING_APP",
                    "app not listed in governance docs",
                    "WARNING",
                    "documentation_alignment",
                )

        # registry_consistency + governance_status
        if registry_entry is not None:
            app_path = registry_entry.get("app_path")
            if not isinstance(app_path, str) or not app_path.strip():
                _add_finding(
                    findings,
                    name,
                    "REGISTRY_APP_PATH_MISSING",
                    "registry app_path missing",
                    "ERROR",
                    "registry_consistency",
                )
            else:
                path_obj = Path(app_path)
                if not path_obj.exists():
                    _add_finding(
                        findings,
                        name,
                        "REGISTRY_APP_PATH_NOT_FOUND",
                        "registry app_path not found",
                        "ERROR",
                        "registry_consistency",
                    )
                elif path_obj.name != name:
                    _add_finding(
                        findings,
                        name,
                        "REGISTRY_NAME_PATH_MISMATCH",
                        "registry name mismatch with app_path",
                        "ERROR",
                        "registry_consistency",
                    )

            status = registry_entry.get("status")
            if status in (None, ""):
                _add_finding(findings, name, "UNKNOWN_STATUS", "unknown status", "WARNING", "governance_status")
            elif status not in ALLOWED_STATUS:
                _add_finding(findings, name, "UNKNOWN_STATUS", "unknown status", "WARNING", "governance_status")
            if status == "active" and not bool(registry_entry.get("verified", False)):
                _add_finding(
                    findings,
                    name,
                    "ACTIVE_NOT_VERIFIED",
                    "active app is not verified",
                    "WARNING",
                    "governance_status",
                )

            # classification_policy
            class_name = registry_entry.get("class")
            primary_role = registry_entry.get("primary_role")
            internal_customer = registry_entry.get("internal_customer")
            external_potential = registry_entry.get("external_product_potential")
            stage = registry_entry.get("productization_stage")
            class_assigned_by = registry_entry.get("class_assigned_by")
            class_assigned_at = registry_entry.get("class_assigned_at")
            reclassification_reason = registry_entry.get("reclassification_reason")
            history = registry_entry.get("reclassification_history")

            if class_name in (None, ""):
                _add_finding(findings, name, "CLASS_MISSING", "missing class metadata", "WARNING", "classification_policy")
            elif not isinstance(class_name, str) or class_name not in VALID_CLASSES:
                _add_finding(findings, name, "CLASS_INVALID", "invalid class value", "ERROR", "classification_policy")
            elif "," in class_name:
                _add_finding(findings, name, "CLASS_INVALID", "multiple class values are not allowed", "ERROR", "classification_policy")

            if not isinstance(primary_role, str) or not primary_role.strip():
                _add_finding(
                    findings,
                    name,
                    "PRIMARY_ROLE_MISSING",
                    "missing primary_role metadata",
                    "WARNING",
                    "classification_policy",
                )

            if internal_customer in (None, ""):
                _add_finding(
                    findings,
                    name,
                    "INTERNAL_CUSTOMER_MISSING",
                    "missing internal_customer metadata",
                    "WARNING",
                    "classification_policy",
                )
            elif isinstance(internal_customer, list):
                bad_item = any(not isinstance(item, str) or not item.strip() for item in internal_customer)
                if bad_item:
                    _add_finding(
                        findings,
                        name,
                        "INTERNAL_CUSTOMER_INVALID",
                        "internal_customer metadata is invalid",
                        "ERROR",
                        "classification_policy",
                    )
            elif not isinstance(internal_customer, str):
                _add_finding(
                    findings,
                    name,
                    "INTERNAL_CUSTOMER_INVALID",
                    "internal_customer metadata is invalid",
                    "ERROR",
                    "classification_policy",
                )

            if external_potential in (None, ""):
                _add_finding(
                    findings,
                    name,
                    "EXTERNAL_PRODUCT_POTENTIAL_MISSING",
                    "missing external_product_potential metadata",
                    "WARNING",
                    "classification_policy",
                )
            elif external_potential not in VALID_EXTERNAL_PRODUCT_POTENTIAL:
                _add_finding(
                    findings,
                    name,
                    "EXTERNAL_PRODUCT_POTENTIAL_INVALID",
                    "invalid external_product_potential value",
                    "ERROR",
                    "classification_policy",
                )

            if stage in (None, ""):
                _add_finding(
                    findings,
                    name,
                    "PRODUCTIZATION_STAGE_MISSING",
                    "missing productization_stage metadata",
                    "WARNING",
                    "classification_policy",
                )
            elif stage not in VALID_PRODUCTIZATION_STAGE:
                _add_finding(
                    findings,
                    name,
                    "PRODUCTIZATION_STAGE_INVALID",
                    "invalid productization_stage value",
                    "ERROR",
                    "classification_policy",
                )

            if history is not None and not isinstance(history, list):
                _add_finding(
                    findings,
                    name,
                    "RECLASS_HISTORY_INVALID",
                    "reclassification_history must be a list",
                    "ERROR",
                    "classification_policy",
                )

            if isinstance(history, list) and any(not isinstance(item, dict) for item in history):
                _add_finding(
                    findings,
                    name,
                    "RECLASS_HISTORY_INVALID",
                    "reclassification_history contains invalid items",
                    "ERROR",
                    "classification_policy",
                )

            if class_name == "dual_role_product":
                history_count = len(history) if isinstance(history, list) else 0
                if history_count == 0 and not reclassification_reason:
                    _add_finding(
                        findings,
                        name,
                        "BIRTH_CLASS_RULE_VIOLATION",
                        "dual_role_product has no promotion evidence",
                        "ERROR",
                        "classification_policy",
                    )

            if class_assigned_by in (None, ""):
                _add_finding(
                    findings,
                    name,
                    "RECLASS_ASSIGNED_BY_MISSING",
                    "missing class_assigned_by metadata",
                    "WARNING",
                    "classification_policy",
                )
            if class_assigned_at in (None, ""):
                _add_finding(
                    findings,
                    name,
                    "RECLASS_ASSIGNED_AT_MISSING",
                    "missing class_assigned_at metadata",
                    "WARNING",
                    "classification_policy",
                )
            if isinstance(history, list) and len(history) > 0 and not reclassification_reason:
                _add_finding(
                    findings,
                    name,
                    "RECLASS_REASON_MISSING",
                    "missing reclassification_reason metadata",
                    "WARNING",
                    "classification_policy",
                )

            # promotion_guard
            if class_name == "dual_role_product":
                if not tests_present:
                    _add_finding(
                        findings,
                        name,
                        "DUAL_ROLE_TESTS_REQUIRED",
                        "dual_role_product requires tests",
                        "ERROR",
                        "promotion_guard",
                    )
                if not cli_present:
                    _add_finding(
                        findings,
                        name,
                        "DUAL_ROLE_CLI_REQUIRED",
                        "dual_role_product requires CLI",
                        "ERROR",
                        "promotion_guard",
                    )
                if not json_signal:
                    _add_finding(
                        findings,
                        name,
                        "DUAL_ROLE_JSON_REQUIRED",
                        "dual_role_product requires machine-readable output support",
                        "ERROR",
                        "promotion_guard",
                    )
                if not _has_product_signal(readme_text):
                    _add_finding(
                        findings,
                        name,
                        "DUAL_ROLE_README_SIGNAL_WEAK",
                        "README has weak product signal for dual_role_product",
                        "WARNING",
                        "promotion_guard",
                    )
                if stage not in DUAL_ROLE_MIN_STAGES:
                    _add_finding(
                        findings,
                        name,
                        "DUAL_ROLE_STAGE_TOO_LOW",
                        "dual_role_product requires product_candidate or market_ready_candidate stage",
                        "ERROR",
                        "promotion_guard",
                    )

            # stage / class consistency
            if class_name == "dual_role_product" and stage == "experimental_lab":
                _add_finding(
                    findings,
                    name,
                    "STAGE_CLASS_CONFLICT",
                    "dual_role_product cannot be experimental_lab",
                    "ERROR",
                    "classification_policy",
                )
            if class_name == "internal_infra" and stage == "market_ready_candidate":
                _add_finding(
                    findings,
                    name,
                    "STAGE_CLASS_CONFLICT",
                    "internal_infra at market_ready_candidate requires explicit exception",
                    "WARNING",
                    "classification_policy",
                )
            if class_name == "worker" and stage == "market_ready_candidate":
                _add_finding(
                    findings,
                    name,
                    "STAGE_CLASS_CONFLICT",
                    "worker at market_ready_candidate requires promotion review",
                    "WARNING",
                    "classification_policy",
                )

            # cross_surface_alignment
            if isinstance(primary_role, str) and primary_role.strip() and readme_text:
                if not _primary_role_aligned(primary_role, readme_text):
                    _add_finding(
                        findings,
                        name,
                        "PRIMARY_ROLE_README_MISMATCH",
                        "README does not reflect primary_role metadata",
                        "WARNING",
                        "cross_surface_alignment",
                    )

        if app_dir is None and name in documented_workers:
            _add_finding(
                findings,
                name,
                "DOCS_WORKER_NOT_FOUND",
                "documented worker missing in apps/",
                "WARNING",
                "documentation_alignment",
            )

        errors, warnings = _build_issue_lists(findings)
        if errors:
            level = "ERROR"
            issues = errors
        elif warnings:
            level = "WARNING"
            issues = warnings
        else:
            level = "OK"
            issues = []

        suggestions = []
        seen_codes: set[str] = set()
        for finding in findings:
            code = finding["code"]
            if code in seen_codes:
                continue
            seen_codes.add(code)
            suggestions.append(_suggestion_for_code(code))

        checks.append(
            {
                "app": name,
                "level": level,
                "issues": issues,
                "suggestions": suggestions,
                "findings": findings,
            }
        )

    summary = {
        "total": len(checks),
        "ok": sum(1 for item in checks if item["level"] == "OK"),
        "warning": sum(1 for item in checks if item["level"] == "WARNING"),
        "error": sum(1 for item in checks if item["level"] == "ERROR"),
    }
    overall = "FAIL" if summary["error"] > 0 else "PASS"

    return {
        "total": summary["total"],
        "ok": summary["ok"],
        "warning": summary["warning"],
        "error": summary["error"],
        "overall": overall,
        "checks": checks,
        "rule_order": RULE_ORDER,
    }
