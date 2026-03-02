from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json


@dataclass(frozen=True)
class Plan:
    version: str
    profile: str | None
    policy_path: str
    actions: list[dict[str, Any]]


def load_plan(path: Path) -> dict[str, Any]:
    # BOM-safe JSON read
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_plan_obj(plan: Any) -> tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "plan.json must be an object"
    if plan.get("version") != "0.1":
        return False, f"unsupported plan version: {plan.get('version')!r}"
    actions = plan.get("actions")
    if not isinstance(actions, list):
        return False, "actions must be a list"
    for i, a in enumerate(actions):
        if not isinstance(a, dict):
            return False, f"action[{i}] must be an object"
        if a.get("type") != "run":
            return False, f"action[{i}] unsupported type: {a.get('type')!r}"
        if "cmd" not in a:
            return False, f"action[{i}] missing cmd"
    return True, "OK"
