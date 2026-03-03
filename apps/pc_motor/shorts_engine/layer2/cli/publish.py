from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.version import __version__


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[3]


def _journal_default(repo_root: Path) -> Path:
    return repo_root / "shorts_engine" / "layer2" / "data" / "publish_journal.jsonl"


def _candidate_runs_dirs(repo_root: Path) -> list[Path]:
    out = [repo_root / "runs", repo_root / "shorts_engine" / "runs", Path.cwd() / "runs"]
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in out:
        k = str(p.resolve()) if p.exists() else str(p)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    return uniq


def _find_run_meta(run_id: str, repo_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    for rd in _candidate_runs_dirs(repo_root):
        mp = rd / run_id / "meta.json"
        if mp.exists():
            try:
                obj = json.loads(mp.read_text(encoding="utf-8-sig"))
                if isinstance(obj, dict):
                    return mp, obj
            except Exception:
                return mp, None
    return None, None


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.publish")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add", help="append publish journal record")
    a.add_argument("--repo-root", dest="repo_root")
    a.add_argument("--journal", dest="journal")
    a.add_argument("--run-id", dest="run_id")
    a.add_argument("--title", dest="title", default="")
    a.add_argument("--mp4-path", dest="mp4_path")
    a.add_argument("--thumb-path", dest="thumb_path")
    a.add_argument("--platform", dest="platform", default="youtube")
    a.add_argument("--url", dest="url")
    a.add_argument("--note", dest="note")

    l = sub.add_parser("list", help="list recent publish records")
    l.add_argument("--repo-root", dest="repo_root")
    l.add_argument("--journal", dest="journal")
    l.add_argument("--limit", dest="limit", type=int, default=20)
    return p.parse_args(argv)


def _cmd_add(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_from_file()
    journal = Path(args.journal) if args.journal else _journal_default(repo_root)
    if not journal.is_absolute():
        journal = (Path.cwd() / journal).resolve()

    mp4_path = str(args.mp4_path or "").strip() or None
    thumb_path = str(args.thumb_path or "").strip() or None
    if args.run_id and (not mp4_path or not thumb_path):
        _, meta = _find_run_meta(str(args.run_id), repo_root)
        if isinstance(meta, dict):
            if not mp4_path:
                arts = meta.get("artifacts")
                if isinstance(arts, dict):
                    v = arts.get("mp4_path")
                    if isinstance(v, str) and v.strip():
                        mp4_path = v.strip()
            if not thumb_path:
                arts = meta.get("artifacts")
                if isinstance(arts, dict):
                    v = arts.get("thumb_path")
                    if isinstance(v, str) and v.strip():
                        thumb_path = v.strip()

    rec = {
        "created_at": _iso_now(),
        "run_id": str(args.run_id).strip() if args.run_id else None,
        "title": str(args.title or ""),
        "platform": str(args.platform or "youtube"),
        "mp4_path": mp4_path,
        "thumb_path": thumb_path,
        "url": str(args.url).strip() if args.url else None,
        "note": str(args.note).strip() if args.note else None,
    }
    _append_jsonl(journal, rec)
    print(f"publish add: journal={journal}")
    print(json.dumps({"ok": True, "exit_code": 0, "journal": str(journal), "record": rec}, ensure_ascii=False))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_from_file()
    journal = Path(args.journal) if args.journal else _journal_default(repo_root)
    if not journal.is_absolute():
        journal = (Path.cwd() / journal).resolve()
    rows: list[dict[str, Any]] = []
    if journal.exists():
        for ln in journal.read_text(encoding="utf-8-sig").splitlines():
            s = ln.strip()
            if not s:
                continue
            try:
                o = json.loads(s)
                if isinstance(o, dict):
                    rows.append(o)
            except Exception:
                continue
    lim = int(args.limit) if args.limit is not None else 20
    if lim > 0:
        rows = rows[-lim:]
    print(f"publish list: count={len(rows)}")
    print(json.dumps({"ok": True, "exit_code": 0, "count": len(rows), "items": rows}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        if args.cmd == "add":
            return _cmd_add(args)
        if args.cmd == "list":
            return _cmd_list(args)
        print("ERROR: missing subcommand (add|list)")
        return 2
    except SystemExit as e:
        try:
            return int(getattr(e, "code", 2))
        except Exception:
            return 2
    except Exception as e:
        print(f"ERROR: {e}")
        print(json.dumps({"ok": False, "exit_code": 1, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
