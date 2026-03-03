from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..core.version import __version__

RUN_ID_RE = re.compile(r"^[0-9a-fA-F]{8,16}$")


@dataclass
class RunInfo:
    run_id: str
    path: Path
    ts: datetime
    failed: bool
    failure_reason: str | None


@dataclass
class BatchInfo:
    batch_id: str
    path: Path
    ts: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _is_run_dir_candidate(path: Path) -> bool:
    if not path.is_dir():
        return False
    if not RUN_ID_RE.match(path.name):
        return False
    if not (path / "meta.json").exists():
        return False
    return True


def _is_batch_dir_candidate(path: Path) -> bool:
    if not path.is_dir():
        return False
    if not path.name:
        return False
    if not (path / "batch_report.json").exists():
        return False
    return True


def _run_failed(meta: dict[str, Any]) -> tuple[bool, str | None]:
    et = meta.get("error_type")
    if et is not None and str(et).strip().lower() not in ("", "none", "null"):
        return True, f"error_type={et}"
    artifacts = meta.get("artifacts")
    if isinstance(artifacts, dict):
        if artifacts.get("artifacts_ok") is False:
            return True, "artifacts_ok=false"
    return False, None


def _run_timestamp(meta: dict[str, Any], fallback_path: Path) -> datetime:
    d = _parse_iso(meta.get("started_at"))
    if d is not None:
        return d
    return _mtime_utc(fallback_path)


def _batch_timestamp(report: dict[str, Any], fallback_path: Path) -> datetime:
    d = _parse_iso(report.get("started_at"))
    if d is not None:
        return d
    return _mtime_utc(fallback_path)


def _safe_rmtree(path: Path, *, retries: int = 3, delay_sec: float = 0.2) -> bool:
    for i in range(max(1, retries)):
        try:
            shutil.rmtree(path)
            return True
        except Exception:
            if i + 1 >= retries:
                return False
            time.sleep(delay_sec)
    return False


def _repo_root_from_file() -> Path:
    # shorts_engine/layer2/cli/clean_runs.py -> repo root parent of shorts_engine
    return Path(__file__).resolve().parents[3]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.clean_runs")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--repo-root", dest="repo_root", help="repo root path")
    p.add_argument("--runs-dir", dest="runs_dir", help="runs directory (default: <repo-root>/runs)")
    p.add_argument("--keep-last", dest="keep_last", type=int, default=50, help="keep newest N runs (default: 50)")
    p.add_argument("--keep-days", dest="keep_days", type=int, default=14, help="keep runs newer than D days (default: 14)")
    p.add_argument("--keep-failed", dest="keep_failed", action="store_true", default=True, help="never delete failed runs")
    p.add_argument("--no-keep-failed", dest="keep_failed", action="store_false", help="allow failed runs to be deleted")
    p.add_argument("--keep-batch-last", dest="keep_batch_last", type=int, default=20, help="keep newest N batch runs")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True, help="plan only (default)")
    p.add_argument("--apply", dest="apply", action="store_true", help="actually delete selected dirs")
    p.add_argument("--json-out", dest="json_out", help="optional cleanup_report.json path")
    return p.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> str | None:
    if args.keep_last < 0:
        return "--keep-last must be >= 0"
    if args.keep_days < 0:
        return "--keep-days must be >= 0"
    if args.keep_batch_last < 0:
        return "--keep-batch-last must be >= 0"
    return None


def _discover_runs(runs_dir: Path) -> list[RunInfo]:
    out: list[RunInfo] = []
    if not runs_dir.exists() or not runs_dir.is_dir():
        return out
    for p in sorted(runs_dir.iterdir(), key=lambda x: x.name):
        if p.name == "_batch":
            continue
        if not _is_run_dir_candidate(p):
            continue
        meta = _load_json(p / "meta.json") or {}
        failed, reason = _run_failed(meta)
        ts = _run_timestamp(meta, p)
        out.append(RunInfo(run_id=p.name, path=p, ts=ts, failed=failed, failure_reason=reason))
    out.sort(key=lambda r: r.ts, reverse=True)
    return out


def _discover_batches(runs_dir: Path) -> list[BatchInfo]:
    out: list[BatchInfo] = []
    batch_root = runs_dir / "_batch"
    if not batch_root.exists() or not batch_root.is_dir():
        return out
    for p in sorted(batch_root.iterdir(), key=lambda x: x.name):
        if not _is_batch_dir_candidate(p):
            continue
        rep = _load_json(p / "batch_report.json") or {}
        ts = _batch_timestamp(rep, p)
        out.append(BatchInfo(batch_id=p.name, path=p, ts=ts))
    out.sort(key=lambda b: b.ts, reverse=True)
    return out


def _build_cleanup_plan(
    runs: list[RunInfo],
    batches: list[BatchInfo],
    *,
    keep_last: int,
    keep_days: int,
    keep_failed: bool,
    keep_batch_last: int,
) -> tuple[list[RunInfo], list[BatchInfo], dict[str, str]]:
    kept_reasons: dict[str, str] = {}
    keep_run_ids: set[str] = set()

    for r in runs[:keep_last]:
        keep_run_ids.add(r.run_id)
        kept_reasons[r.run_id] = "keep_last"

    if keep_days >= 0:
        cut = _utc_now() - timedelta(days=keep_days)
        for r in runs:
            if r.ts >= cut:
                keep_run_ids.add(r.run_id)
                kept_reasons[r.run_id] = "keep_days"

    if keep_failed:
        for r in runs:
            if r.failed:
                keep_run_ids.add(r.run_id)
                kept_reasons[r.run_id] = r.failure_reason or "keep_failed"

    delete_runs = [r for r in runs if r.run_id not in keep_run_ids]
    keep_batches = set(b.batch_id for b in batches[:keep_batch_last])
    delete_batches = [b for b in batches if b.batch_id not in keep_batches]
    return delete_runs, delete_batches, kept_reasons


def _write_json_report(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        err = _validate_args(args)
        if err:
            payload = {
                "ok": False,
                "exit_code": 2,
                "runs_dir": None,
                "dry_run": True,
                "policy": {
                    "keep_last": int(args.keep_last),
                    "keep_days": int(args.keep_days),
                    "keep_failed": bool(args.keep_failed),
                    "keep_batch_last": int(args.keep_batch_last),
                },
                "counts": {
                    "scanned_runs": 0,
                    "scanned_batches": 0,
                    "delete_runs": 0,
                    "delete_batches": 0,
                    "kept_runs": 0,
                    "kept_batches": 0,
                },
                "deleted": {"runs": [], "batches": []},
                "kept_reasons": {},
                "error": err,
            }
            print(f"ERROR: {err}")
            _write_json_report(args.json_out, payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 2

        repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_from_file()
        runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else (repo_root / "runs")
        dry_run = (not bool(args.apply)) if args.apply else True

        runs = _discover_runs(runs_dir)
        batches = _discover_batches(runs_dir)
        delete_runs, delete_batches, kept_reasons = _build_cleanup_plan(
            runs,
            batches,
            keep_last=int(args.keep_last),
            keep_days=int(args.keep_days),
            keep_failed=bool(args.keep_failed),
            keep_batch_last=int(args.keep_batch_last),
        )

        deleted_runs: list[str] = []
        deleted_batches: list[str] = []
        if not dry_run:
            for r in delete_runs:
                if _safe_rmtree(r.path):
                    deleted_runs.append(r.run_id)
            for b in delete_batches:
                if _safe_rmtree(b.path):
                    deleted_batches.append(b.batch_id)
        else:
            deleted_runs = [r.run_id for r in delete_runs]
            deleted_batches = [b.batch_id for b in delete_batches]

        payload: dict[str, Any] = {
            "ok": True,
            "exit_code": 0,
            "runs_dir": str(runs_dir),
            "dry_run": dry_run,
            "policy": {
                "keep_last": int(args.keep_last),
                "keep_days": int(args.keep_days),
                "keep_failed": bool(args.keep_failed),
                "keep_batch_last": int(args.keep_batch_last),
            },
            "counts": {
                "scanned_runs": len(runs),
                "scanned_batches": len(batches),
                "delete_runs": len(delete_runs),
                "delete_batches": len(delete_batches),
                "kept_runs": max(0, len(runs) - len(delete_runs)),
                "kept_batches": max(0, len(batches) - len(delete_batches)),
            },
            "deleted": {"runs": deleted_runs, "batches": deleted_batches},
            "kept_reasons": dict(list(kept_reasons.items())[:500]),
            "generated_at": _iso_now(),
        }

        print(
            "clean_runs: "
            f"runs scanned={len(runs)} delete={len(delete_runs)} kept={len(runs) - len(delete_runs)}; "
            f"batches scanned={len(batches)} delete={len(delete_batches)} kept={len(batches) - len(delete_batches)}; "
            f"dry_run={dry_run}"
        )
        _write_json_report(args.json_out, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as e:
        payload = {
            "ok": False,
            "exit_code": 1,
            "runs_dir": None,
            "dry_run": True,
            "policy": {},
            "counts": {
                "scanned_runs": 0,
                "scanned_batches": 0,
                "delete_runs": 0,
                "delete_batches": 0,
                "kept_runs": 0,
                "kept_batches": 0,
            },
            "deleted": {"runs": [], "batches": []},
            "kept_reasons": {},
            "error": str(e),
        }
        print(f"ERROR: {e}")
        print(json.dumps(payload, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
