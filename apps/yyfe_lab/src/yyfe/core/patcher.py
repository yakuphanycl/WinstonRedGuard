from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_FILE_HEADER = re.compile(r"^\+\+\+\s+b/(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Patch:
    diff: str

    def touched_files(self) -> list[str]:
        return _FILE_HEADER.findall(self.diff)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.diff, encoding="utf-8")
