from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _walk(obj: Any, prefix: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        req = obj.get("required")
        props = obj.get("properties")
        if isinstance(req, list):
            out.append(f"{prefix}required: {req}")
        if isinstance(props, dict):
            out.append(f"{prefix}properties: {list(props.keys())}")
            for k, v in props.items():
                if isinstance(v, dict) and (v.get("type") == "object" or "properties" in v):
                    out.extend(_walk(v, prefix=prefix + f"{k}."))
    return out


def main() -> int:
    base = Path(__file__).resolve().parents[1] / "shorts_engine" / "layer2"
    schema_path = base / "schemas" / "job_v0_5.json"
    if not schema_path.exists():
        raise SystemExit(f"schema not found: {schema_path}")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    print(f"Schema: {schema_path}")
    print(f"$id: {schema.get('$id')}")
    print(f"title: {schema.get('title')}")
    print(f"type: {schema.get('type')}")
    print("\n--- TOP-LEVEL ---")
    for line in _walk(schema, ""):
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
