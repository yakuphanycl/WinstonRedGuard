from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str


def run(cmd: list[str], cwd: str | Path | None = None) -> RunResult:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return RunResult(
        ok=(p.returncode == 0), exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr
    )
