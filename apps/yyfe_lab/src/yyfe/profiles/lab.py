from __future__ import annotations

from pathlib import Path
from typing import Any


def build_plan(args: Any) -> dict[str, Any]:
    # Minimal plan: just run tools/golden.ps1
    return {
        "version": "0.1",
        "profile": "lab",
        "policy_path": str(args.policy),
        "actions": [
            {
                "id": "golden",
                "type": "run",
                "cmd": [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(Path("tools") / "golden.ps1"),
                ],
            }
        ],
    }
