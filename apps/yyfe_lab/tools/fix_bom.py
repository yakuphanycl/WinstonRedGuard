from __future__ import annotations

from pathlib import Path

BOM = b"\xEF\xBB\xBF"

EXTS = {
    ".ini", ".toml", ".yaml", ".yml", ".json",
    ".md", ".txt", ".ps1", ".py", ".cfg",
}

SKIP_DIRS = {".git", ".venv", "dist", "build", ".pytest_cache", ".tmp", "output", "__pycache__"}

def is_binary_ext(p: Path) -> bool:
    return p.suffix.lower() in {".exe", ".dll", ".pyd", ".so", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".whl"}

def main() -> int:
    root = Path(".").resolve()
    fixed = 0

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if is_binary_ext(p):
            continue
        if p.suffix.lower() not in EXTS:
            continue

        b = p.read_bytes()
        if b.startswith(BOM):
            p.write_bytes(b[len(BOM):])
            fixed += 1
            print(f"FIXED: {p.relative_to(root).as_posix()}")

    print(f"FIX_OK: {fixed} file(s)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
