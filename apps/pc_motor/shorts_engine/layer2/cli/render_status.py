from __future__ import annotations

from pathlib import Path
import json
import sys

def _eprint(*a: object) -> None:
    print(*a, file=sys.stderr)

def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(p.read_text(encoding="utf-8-sig"))

def main(argv: list[str]) -> int:
    runs = Path("runs")
    if not runs.exists():
        _eprint("No runs/ directory.")
        return 2

    dirs = [d for d in runs.iterdir() if d.is_dir()]
    if not dirs:
        _eprint("No runs found.")
        return 2

    latest = sorted(dirs, key=lambda d: d.stat().st_mtime, reverse=True)[0]
    meta = latest / "meta.json"
    if not meta.exists():
        _eprint(f"Latest run has no meta.json: {latest}")
        return 2

    m = _read_json(meta)
    print(f"run_id={m.get('run_id', latest.name)} rc={m.get('rc')} out={m.get('requested_out')}")
    print(f"run_dir={latest}")
    stdout = latest / "stdout.log"
    if stdout.exists():
        print(f"stdout={stdout}")
    trace = latest / "trace.txt"
    if trace.exists():
        print(f"trace={trace}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
