from __future__ import annotations

import json
from pathlib import Path

from .checker import build_governance_report


def run_check(repo_root: str | Path | None = None) -> dict:
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    return build_governance_report(root)


def format_human_report(report: dict) -> str:
    lines = ["governance check:"]
    for item in report["checks"]:
        level = str(item["level"]).upper()
        if item["issues"]:
            lines.append(f"- {item['app']}: {level} {', '.join(item['issues'])}")
        else:
            lines.append(f"- {item['app']}: {level}")
    lines.append(
        "summary: total={total} ok={ok} warning={warning} error={error} overall={overall}".format(
            total=report["total"],
            ok=report["ok"],
            warning=report["warning"],
            error=report["error"],
            overall=report["overall"],
        )
    )
    return "\n".join(lines)


def write_json_report(report: dict, output_path: str | Path) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
