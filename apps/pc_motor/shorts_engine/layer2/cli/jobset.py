from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.version import __version__


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _job_hash(job_obj: dict[str, Any]) -> str:
    return _sha256_text(_stable_json(job_obj))


def _norm_path(p: Path) -> str:
    try:
        return str(p.resolve()).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _job_duration(job_obj: dict[str, Any]) -> int | None:
    v = job_obj.get("video")
    if not isinstance(v, dict):
        return None
    d = v.get("duration_sec")
    if isinstance(d, (int, float)) and d >= 0:
        return int(round(float(d)))
    return None


def _job_contains_text(job_obj: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    q = needle.lower()
    subtitles = job_obj.get("subtitles")
    if isinstance(subtitles, dict):
        items = subtitles.get("items")
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    t = it.get("text")
                    if isinstance(t, str) and q in t.lower():
                        return True
    return False


def _scan_jobs(*, jobs_dir: str | None, glob_pat: str, jobs_file: str | None) -> list[Path]:
    out: list[Path] = []
    if jobs_file:
        p = Path(jobs_file)
        if not p.exists():
            raise ValueError(f"jobs-file not found: {p}")
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip()
            if not s:
                continue
            jp = Path(s)
            if jp.exists() and jp.is_file():
                out.append(jp)
    if jobs_dir:
        d = Path(jobs_dir)
        if not d.exists() or not d.is_dir():
            raise ValueError(f"jobs-dir not found or not a directory: {d}")
        out.extend([p for p in d.rglob(glob_pat) if p.is_file()])
    uniq: dict[str, Path] = {}
    for p in out:
        uniq[_norm_path(p)] = p
    return [uniq[k] for k in sorted(uniq.keys())]


def _jobset_hash(*, jobs: list[dict[str, Any]], filters: dict[str, Any], source: dict[str, Any]) -> str:
    payload = {
        "jobs": [{"job_path": j.get("job_path")} for j in jobs],
        "filters": filters,
        "source": source,
    }
    return _sha256_text(_stable_json(payload))


def _cmd_build(args: argparse.Namespace) -> int:
    if not args.jobs_dir and not args.jobs_file:
        print("ERROR: build requires --jobs-dir and/or --jobs-file")
        return 2
    if not args.out:
        print("ERROR: build requires --out")
        return 2
    if args.min_duration is not None and args.min_duration < 0:
        print("ERROR: --min-duration must be >= 0")
        return 2
    if args.max_duration is not None and args.max_duration < 0:
        print("ERROR: --max-duration must be >= 0")
        return 2
    if args.limit is not None and args.limit < 1:
        print("ERROR: --limit must be >= 1")
        return 2

    try:
        paths = _scan_jobs(jobs_dir=args.jobs_dir, glob_pat=args.glob_pat, jobs_file=args.jobs_file)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2

    scanned = len(paths)
    selected: list[dict[str, Any]] = []

    for p in paths:
        obj = _read_json(p)
        if not isinstance(obj, dict):
            continue
        if args.only_version:
            if str(obj.get("version", "")).strip() != str(args.only_version).strip():
                continue
        dur = _job_duration(obj)
        if args.min_duration is not None and (dur is None or dur < int(args.min_duration)):
            continue
        if args.max_duration is not None and (dur is None or dur > int(args.max_duration)):
            continue
        if args.contains_text and not _job_contains_text(obj, str(args.contains_text)):
            continue
        selected.append(
            {
                "job_path": _norm_path(p),
                "job_hash": _job_hash(obj),
                "duration_sec": dur,
            }
        )

    selected.sort(key=lambda x: str(x.get("job_path") or ""))
    if args.limit is not None:
        selected = selected[: int(args.limit)]

    source = {
        "jobs_dir": _norm_path(Path(args.jobs_dir)) if args.jobs_dir else None,
        "glob": args.glob_pat if args.glob_pat else None,
        "jobs_file": _norm_path(Path(args.jobs_file)) if args.jobs_file else None,
    }
    filters = {
        "only_version": args.only_version if args.only_version else None,
        "min_duration": int(args.min_duration) if args.min_duration is not None else None,
        "max_duration": int(args.max_duration) if args.max_duration is not None else None,
        "contains_text": args.contains_text if args.contains_text else None,
        "limit": int(args.limit) if args.limit is not None else None,
    }
    payload = {
        "schema_version": "0.1",
        "created_at": _iso_now(),
        "jobset_hash": _jobset_hash(jobs=selected, filters=filters, source=source),
        "source": source,
        "filters": filters,
        "jobs": selected,
        "counts": {"scanned": scanned, "selected": len(selected)},
    }
    out_path = Path(args.out)
    if out_path.parent and str(out_path.parent) not in ("", "."):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"jobset build: scanned={scanned} selected={len(selected)} out={out_path}")
    print(json.dumps({"ok": True, "exit_code": 0, "jobset_path": str(out_path), "jobset_hash": payload["jobset_hash"]}, ensure_ascii=False))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    if not args.jobset:
        print("ERROR: inspect requires --jobset")
        return 2
    p = Path(args.jobset)
    if not p.exists():
        print(f"ERROR: jobset not found: {p}")
        return 2
    obj = _read_json(p)
    if not isinstance(obj, dict):
        print(f"ERROR: invalid jobset json: {p}")
        return 2
    jobs = obj.get("jobs")
    if not isinstance(jobs, list):
        print("ERROR: invalid jobset: missing jobs[]")
        return 2
    counts = obj.get("counts") if isinstance(obj.get("counts"), dict) else {"selected": len(jobs)}
    preview = []
    for it in jobs[:5]:
        if isinstance(it, dict):
            preview.append({"job_path": it.get("job_path"), "duration_sec": it.get("duration_sec")})
    print(f"jobset inspect: selected={len(jobs)} hash={obj.get('jobset_hash')}")
    out = {
        "ok": True,
        "exit_code": 0,
        "counts": counts,
        "jobset_hash": obj.get("jobset_hash"),
        "jobs_preview": preview,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _cmd_emit_list(args: argparse.Namespace) -> int:
    if not args.jobset or not args.out:
        print("ERROR: emit-list requires --jobset and --out")
        return 2
    p = Path(args.jobset)
    if not p.exists():
        print(f"ERROR: jobset not found: {p}")
        return 2
    obj = _read_json(p)
    if not isinstance(obj, dict):
        print(f"ERROR: invalid jobset json: {p}")
        return 2
    jobs = obj.get("jobs")
    if not isinstance(jobs, list):
        print("ERROR: invalid jobset: missing jobs[]")
        return 2
    lines: list[str] = []
    for it in jobs:
        if not isinstance(it, dict):
            continue
        jp = it.get("job_path")
        if isinstance(jp, str) and jp.strip():
            lines.append(jp.strip())
    out = Path(args.out)
    if out.parent and str(out.parent) not in ("", "."):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"jobset emit-list: count={len(lines)} out={out}")
    print(json.dumps({"ok": True, "exit_code": 0, "count": len(lines), "out": str(out)}, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.jobset")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="build deterministic jobset from job sources")
    b.add_argument("--jobs-dir", dest="jobs_dir", help="scan jobs dir recursively")
    b.add_argument("--glob", dest="glob_pat", default="*.json", help="glob pattern for jobs-dir scan")
    b.add_argument("--jobs-file", dest="jobs_file", help="newline-separated jobs file")
    b.add_argument("--only-version", dest="only_version", help="filter by job.version")
    b.add_argument("--min-duration", dest="min_duration", type=int, help="minimum video.duration_sec")
    b.add_argument("--max-duration", dest="max_duration", type=int, help="maximum video.duration_sec")
    b.add_argument("--contains-text", dest="contains_text", help="substring search in subtitles text")
    b.add_argument("--limit", dest="limit", type=int, help="limit selected jobs")
    b.add_argument("--out", dest="out", help="output jobset path")

    i = sub.add_parser("inspect", help="inspect jobset")
    i.add_argument("--jobset", dest="jobset", help="jobset json path")

    e = sub.add_parser("emit-list", help="emit plain jobs list from jobset")
    e.add_argument("--jobset", dest="jobset", help="jobset json path")
    e.add_argument("--out", dest="out", help="output list path")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)
        if not args.cmd:
            parser.print_help()
            return 2
        if args.cmd == "build":
            return _cmd_build(args)
        if args.cmd == "inspect":
            return _cmd_inspect(args)
        if args.cmd == "emit-list":
            return _cmd_emit_list(args)
        print(f"ERROR: unknown subcommand: {args.cmd}")
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
