from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Policy:
    engine: str
    version: str
    max_files_per_patch: int
    max_patch_lines: int
    allowed_commands: list[str]
    forbidden_patterns: list[str]

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return cls(
            engine=str(data.get("engine", "YY-FE")),
            version=str(data.get("version", "0.0")),
            max_files_per_patch=int(data.get("max_files_per_patch", 1)),
            max_patch_lines=int(data.get("max_patch_lines", 300)),
            allowed_commands=list(data.get("allowed_commands", [])),
            forbidden_patterns=list(data.get("forbidden_patterns", [])),
        )

    def check_command(self, cmd: str) -> None:
        ok = any(cmd.strip().lower().startswith(a.lower()) for a in self.allowed_commands)
        if not ok:
            raise ValueError(f"Command not allowed by policy: {cmd}")

        low = cmd.lower()
        for pat in self.forbidden_patterns:
            if pat.lower() in low:
                raise ValueError(f"Command blocked by forbidden pattern: {pat}")

    def check_diff_constraints(self, changed_files: Iterable[str], diff_text: str) -> None:
        files = list(dict.fromkeys(changed_files))
        if len(files) > self.max_files_per_patch:
            raise ValueError(
                f"Patch touches too many files ({len(files)} > {self.max_files_per_patch})"
            )

        lines = diff_text.splitlines()
        if len(lines) > self.max_patch_lines:
            raise ValueError(f"Patch too large ({len(lines)} lines > {self.max_patch_lines})")

        if "GIT binary patch" in diff_text:
            raise ValueError("Binary patches are not allowed")

