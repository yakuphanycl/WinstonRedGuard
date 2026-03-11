from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .orchestrator import list_workflows, run_workflow


def resolve_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "apps").is_dir():
            return candidate
    return cwd


def get_workflows() -> list[str]:
    return list_workflows()


def execute_workflow(workflow_name: str, repo_root: Path) -> dict[str, object]:
    result = run_workflow(workflow_name, repo_root)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result


def write_json_result(result: dict[str, object], json_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf8")

