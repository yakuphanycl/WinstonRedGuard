from __future__ import annotations

from pathlib import Path

from .core import upsert_record


def _repo_root() -> Path:
    return Path.cwd().resolve()


def _app_root(app_name: str) -> Path:
    return _repo_root() / "apps" / app_name


def _contains_json_signal(app_root: Path, app_name: str) -> bool:
    candidates = [app_root / "README.md"]
    src_root = app_root / "src" / app_name
    if src_root.exists():
        candidates.extend(sorted(src_root.rglob("*.py")))

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf8", errors="ignore").lower()
        if "--json-out" in text or "json" in text:
            return True
    return False


def inspect_app(app_name: str) -> dict:
    app_root = _app_root(app_name)
    if not app_root.exists() or not app_root.is_dir():
        raise ValueError(f"app directory not found: apps/{app_name}")

    readme_present = (app_root / "README.md").exists()
    tests_present = (app_root / "tests").exists()
    cli_present = (app_root / "src" / app_name / "cli.py").exists()
    json_output_present = _contains_json_signal(app_root, app_name)

    score = 0
    score += 1 if readme_present else 0
    score += 1 if cli_present else 0
    score += 1 if tests_present else 0
    score += 1 if json_output_present else 0

    return upsert_record(
        app_name,
        {
            "status": "reviewing",
            "product_score": score,
            "readme_present": readme_present,
            "cli_present": cli_present,
            "tests_present": tests_present,
            "json_output_present": json_output_present,
            "last_action": "inspect",
        },
    )
