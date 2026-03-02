from __future__ import annotations

from pathlib import Path
import sys

BOM = b"\xEF\xBB\xBF"

# What we care about: config + text-ish files that often break with BOM
EXTS = {
    ".ini", ".toml", ".yaml", ".yml", ".json",
    ".md", ".txt", ".ps1", ".py", ".cfg",
}

SKIP_DIRS = {".git", ".venv", "dist", "build", ".pytest_cache", ".tmp", "output", "__pycache__"}

def is_binary_ext(p: Path) -> bool:
    # crude: skip common binaries
    return p.suffix.lower() in {".exe", ".dll", ".pyd", ".so", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".whl"}

def main() -> int:
    root = Path(".").resolve()
    bad: list[Path] = []

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if is_binary_ext(p):
            continue
        if p.suffix.lower() not in EXTS:
            continue

        try:
            b = p.read_bytes()
        except OSError:
            continue

        if b.startswith(BOM):
            bad.append(p.relative_to(root))

    if bad:
        print("BOM_FOUND:")
        for p in bad:
            print(f"  - {p.as_posix()}")
        return 2

    print("BOM_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
