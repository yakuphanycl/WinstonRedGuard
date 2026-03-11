from __future__ import annotations

from .core import get_required_record, upsert_record


def build_refine_plan(app_name: str) -> dict:
    row = get_required_record(app_name)
    notes: list[str] = []

    if not bool(row.get("readme_present")):
        notes.append("README ekle")
    if not bool(row.get("tests_present")):
        notes.append("smoke test ekle")
    if not bool(row.get("cli_present")):
        notes.append("entry CLI olustur")
    if not bool(row.get("json_output_present")):
        notes.append("machine-readable cikti ekle")

    return upsert_record(
        app_name,
        {
            "status": "refining",
            "packaging_notes": notes,
            "last_action": "refine-plan",
        },
    )
