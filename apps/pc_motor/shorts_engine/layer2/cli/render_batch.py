from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# IMPORTANT:
# Use package-relative imports so both forms work:
# - python -m layer2.cli.render_batch (cwd=shorts_engine)
# - python -m shorts_engine.layer2.cli.render_batch (cwd=repo parent)
from ..core.errors import classify_exception
from ..core.presets import apply_preset
from ..core.rc import RC_OK, rc_for_error_type
from ..core.schema_meta import schema_meta
from ..core.version import __version__
try:
    from ..core.validate_job import JobValidationError
except Exception:  # pragma: no cover
    class JobValidationError(Exception):
        pass

BATCH_SCHEMA_VERSION = "0.1"
_ALLOWED_ERROR_TYPES = {
    "validation_error",
    "io_error",
    "render_error",
    "timeout",
    "internal_error",
}


def _normalize_error_type(t: str | None, message: str | None = None) -> str:
    if t:
        tt = str(t).strip().lower()
        if tt in _ALLOWED_ERROR_TYPES:
            return tt

    msg = (message or "").lower()

    if "missing required" in msg or "schema" in msg or "validation" in msg:
        return "validation_error"
    if "permission" in msg or "access is denied" in msg or "no such file" in msg or "not found" in msg:
        return "io_error"
    if "ffmpeg" in msg or "exitcode" in msg or "renderer" in msg:
        return "render_error"
    if "timeout" in msg:
        return "timeout"

    return "internal_error"


def _emit_summary(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _print_stdout_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _stdout_error_payload(
    *,
    error_type: str,
    message: str,
    hint: str | None = None,
    exit_code: int = 1,
) -> dict[str, Any]:
    return {
        "ok": False,
        "exit_code": int(exit_code),
        "error": {"type": error_type, "message": message, "hint": hint},
        "report_path": None,
        "items": [],
        "runs": [],
        "summary": None,
        "contract_version": "1",
    }


def _ok_payload_for_help(*, hint: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "exit_code": 0,
        "error": None,
        "report_path": None,
        "items": [],
        "runs": [],
        "summary": None,
        "contract_version": "1",
        "hint": hint,
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _duration_ms(t0: float, t1: float) -> int:
    return int(round((t1 - t0) * 1000))


def _batch_run_id_now() -> str:
    return "batch_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _git_info() -> dict[str, Any]:
    info: dict[str, Any] = {"sha": None, "tag": None, "dirty": None}
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
        s = (r.stdout or "").strip()
        if s:
            info["sha"] = s
    except Exception:
        pass
    try:
        r = subprocess.run(["git", "describe", "--tags", "--exact-match"], capture_output=True, text=True, check=False)
        t = (r.stdout or "").strip()
        if t:
            info["tag"] = t
    except Exception:
        pass
    try:
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False)
        info["dirty"] = bool((r.stdout or "").strip())
    except Exception:
        pass
    return info


def _engine_version() -> str:
    return __version__


def _host_info() -> dict[str, Any]:
    return {"os": platform.system(), "python": sys.version.split()[0]}


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    rank = (max(0.0, min(100.0, p)) / 100.0) * (len(vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(vals) - 1)
    frac = rank - lo
    return float(vals[lo] * (1.0 - frac) + vals[hi] * frac)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m layer2.cli.render_batch")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--jobs-dir", dest="jobs_dir", help="directory containing jobs")
    p.add_argument("--glob", dest="glob_pat", default="*.json", help="glob pattern (default: *.json)")
    p.add_argument("--jobs-file", dest="jobs_file", help="newline-separated job paths")
    p.add_argument("--jobset", dest="jobset", help="jobset json path (jobset_v0_1)")
    p.add_argument("--max", dest="max_jobs", type=int, help="maximum number of jobs")
    p.add_argument("--stop-on-error", action="store_true", help="stop after first failed job")
    p.add_argument("--continue-on-error", action="store_true", help="continue processing after failures")
    p.add_argument("--max-fail", dest="max_fail", type=int, help="stop once failure count reaches this value")
    p.add_argument("--skip-existing", action="store_true", help="skip job if existing status.json is ok=true")
    p.add_argument("--resume", action="store_true", help="resume mode: skip ok=true runs, rerun ok=false runs")
    p.add_argument("--retry-io", dest="retry_io", type=int, default=0, help="retry count for io failures (default: 0)")
    p.add_argument("--retry-delay-ms", dest="retry_delay_ms", type=int, default=0, help="delay between io retries in ms (default: 0)")
    p.add_argument("--only-failed-from", dest="only_failed_from", help="run only failed jobs from a previous batch_report.json")
    p.add_argument("--retry-failed", action="store_true", help="mark selection mode as retry of failed jobs (use with --only-failed-from)")
    p.add_argument("--json-out", dest="json_out", help="optional JSON report output path")
    return p.parse_args(argv)


def _load_jobs_from_file(path: Path) -> tuple[list[str], dict[str, Any]]:
    txt = path.read_text(encoding="utf-8-sig")
    jobs: list[str] = []
    opts: dict[str, Any] = {}
    # JSON manifest mode
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict) and isinstance(obj.get("jobs"), list):
            for it in obj.get("jobs", []):
                if isinstance(it, dict):
                    p = it.get("path")
                    if isinstance(p, str) and p.strip():
                        jobs.append(p.strip())
                elif isinstance(it, str) and it.strip():
                    jobs.append(it.strip())
            ro = obj.get("report_out")
            if isinstance(ro, str) and ro.strip():
                opts["json_out"] = ro.strip()
            cof = obj.get("continue_on_fail")
            if isinstance(cof, bool):
                # render_batch uses stop_on_error; invert.
                opts["stop_on_error"] = (not cof)
            return jobs, opts
    except Exception:
        pass
    # Line list mode
    for raw in txt.splitlines():
        s = raw.strip()
        if not s:
            continue
        jobs.append(s)
    return jobs, opts


def _discover_jobs(args: argparse.Namespace) -> tuple[list[str], str | None, dict[str, Any]]:
    if not args.jobs_dir and not args.jobs_file:
        return [], "missing input: provide --jobs-dir or --jobs-file", {}

    jobs: list[str] = []
    opts: dict[str, Any] = {}
    if args.jobs_file:
        jf = Path(args.jobs_file)
        if not jf.exists():
            return [], f"jobs-file not found: {jf}", {}
        jobs_list, parsed_opts = _load_jobs_from_file(jf)
        jobs.extend(jobs_list)
        opts.update(parsed_opts)
    else:
        jd = Path(args.jobs_dir)
        if not jd.exists() or not jd.is_dir():
            return [], f"jobs-dir not found or not a directory: {jd}", {}
        jobs.extend(str(p) for p in sorted(jd.glob(args.glob_pat)) if p.is_file())

    if args.max_jobs is not None:
        if args.max_jobs < 1:
            return [], "--max must be >= 1", opts
        jobs = jobs[: args.max_jobs]

    if not jobs:
        return [], "no job files found", opts

    return jobs, None, opts


def _jobs_from_failed_report(path: str) -> tuple[list[str], str | None]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return [], f"only-failed-from report not found: {p}"
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return [], f"only-failed-from report invalid JSON: {e}"
    if not isinstance(raw, dict):
        return [], "only-failed-from report root must be object"
    items = raw.get("items")
    if not isinstance(items, list):
        return [], "only-failed-from report missing items[]"
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        job_path = it.get("job_path")
        if not isinstance(job_path, str) or not job_path.strip():
            continue
        rc = it.get("result_rc")
        et = it.get("error_type")
        st = it.get("status")
        failed = False
        if isinstance(rc, int) and rc != 0:
            failed = True
        if isinstance(et, str) and et.strip() and et.strip().lower() != "none":
            failed = True
        if isinstance(st, str) and st.strip().lower() == "fail":
            failed = True
        if not failed:
            continue
        jp = job_path.strip()
        if not Path(jp).exists():
            continue
        if jp in seen:
            continue
        seen.add(jp)
        out.append(jp)
    if not out:
        return [], "only-failed-from produced no existing failed jobs"
    return out, None


def _jobs_from_jobset(path: str) -> tuple[list[str], str | None, str | None]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return [], None, f"jobset not found: {p}"
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return [], None, f"jobset invalid JSON: {e}"
    if not isinstance(raw, dict):
        return [], None, "jobset root must be object"
    items = raw.get("jobs")
    if not isinstance(items, list):
        return [], None, "jobset missing jobs[]"
    out: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        jp = it.get("job_path")
        if isinstance(jp, str) and jp.strip():
            out.append(jp.strip())
    if not out:
        return [], None, "jobset jobs[] is empty"
    return out, (raw.get("jobset_hash") if isinstance(raw.get("jobset_hash"), str) else None), None


_RESULT_RE = re.compile(
    r"RESULT\s+ok\s+rc=(?P<rc>\d+)\s+out=(?P<out>\S+)\s+run_id=(?P<run_id>[0-9a-fA-F_]+)\s+cached=(?P<cached>True|False)",
    re.IGNORECASE,
)


def _parse_render_result(stdout_text: str) -> dict[str, Any]:
    for line in reversed(stdout_text.splitlines()):
        m = _RESULT_RE.search(line.strip())
        if not m:
            continue
        return {
            "result_rc": int(m.group("rc")),
            "out_path": m.group("out"),
            "run_id": m.group("run_id"),
            "cached": m.group("cached").lower() == "true",
        }
    return {}


def _derive_run_id_from_job(job_path: str) -> str | None:
    try:
        p = Path(job_path)
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict):
            effective, _, _ = apply_preset(raw)
        else:
            effective = raw
        s = json.dumps(effective, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return None


def _job_hash_from_job(job_path: str) -> str | None:
    try:
        p = Path(job_path)
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict):
            effective, _, _ = apply_preset(raw)
        else:
            effective = raw
        s = json.dumps(effective, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(s.encode("utf-8")).hexdigest()
    except Exception:
        return None


def _job_output_path(job_path: str) -> str | None:
    try:
        p = Path(job_path)
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
        out = raw.get("output")
        if isinstance(out, dict):
            path_val = out.get("path")
            if isinstance(path_val, str) and path_val.strip():
                return path_val.strip()
    except Exception:
        return None
    return None


def _render_job_module_name() -> str:
    pkg = (__package__ or "").strip()
    if pkg.startswith("shorts_engine."):
        return "shorts_engine.layer2.cli.render_job"
    return "layer2.cli.render_job"


def _read_run_status(run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    try:
        status_path = Path("runs") / run_id / "status.json"
        if not status_path.exists():
            return None
        data = json.loads(status_path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _infer_error_type(stdout_text: str, *, rc: int) -> str:
    if rc == 0:
        return "none"
    s = (stdout_text or "").lower()
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "schema validation failed" in s or "invalid job" in s:
        return "validation_error"
    if "no such file" in s or "not found" in s:
        return "io_error"
    return "internal_error"


def _error_bucket(error_type: str | None) -> str:
    return _normalize_error_type(error_type)


def _build_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    s = {
        "total": len(items),
        "ok": 0,
        "fail": 0,
        "validation_error": 0,
        "io_error": 0,
        "render_error": 0,
        "timeout": 0,
        "internal_error": 0,
    }

    for i in items:
        et = i.get("error_type")
        if et is None and i.get("result_rc") == 0:
            s["ok"] += 1
        elif et in s:
            s[str(et)] += 1
        else:
            s["internal_error"] += 1

    s["fail"] = s["total"] - s["ok"]

    return s


def _count_fail_by_type(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for it in items:
        if it.get("status") != "fail":
            continue
        err = it.get("error") or {}
        t = _normalize_error_type(err.get("type"), err.get("message"))
        counts[t] = counts.get(t, 0) + 1
    return counts


def _build_report(meta: dict[str, Any], summary: dict[str, Any], fail_by_type: dict[str, Any], sample_failures: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        **schema_meta("0.1"),
        "meta": meta,
        "summary": summary,
        "fail_by_type": fail_by_type,
        "sample_failures": sample_failures,
        "items": items,
    }
    return report


def _collect_sample_failures(items: list[dict[str, Any]], max_per_type: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for it in items:
        if it.get("status") != "fail":
            continue
        err = it.get("error") or {}
        t = _normalize_error_type(err.get("type"), err.get("message"))
        if seen.get(t, 0) >= max_per_type:
            continue
        seen[t] = seen.get(t, 0) + 1
        out.append(
            {
                "type": t,
                "job_path": it.get("job_path", ""),
                "message": (err.get("message") or "")[:240],
                "run_id": it.get("run_id"),
                "trace_path": it.get("trace_path"),
            }
        )
    return out


def _make_fail_item(
    job_path: str,
    duration_sec: float,
    err_type: str | None,
    message: str,
    *,
    run_id: str | None = None,
    trace_path: str | None = None,
    code: int | str | None = None,
    detail: Any = None,
) -> dict[str, Any]:
    norm_type = _normalize_error_type(err_type, message)

    item: dict[str, Any] = {
        "job_path": job_path,
        "status": "fail",
        "duration_sec": max(0.0, float(duration_sec)),
        "error": {
            "type": norm_type,
            "message": (message or "").strip()[:500],
        },
    }

    if code is not None:
        item["error"]["code"] = code
    if detail is not None:
        item["error"]["detail"] = detail

    if run_id:
        item["run_id"] = run_id
    if trace_path:
        item["trace_path"] = trace_path

    return item


def _default_trace_path_for_run(run_id: str) -> str:
    return f"runs/{run_id}/trace.txt"


def _attach_run_refs(item: dict[str, Any], run_id: str | None) -> None:
    if not run_id:
        return
    item["run_id"] = run_id
    item.setdefault("trace_path", _default_trace_path_for_run(run_id))


def _write_batch_report(path: str | Path, items: list[dict[str, Any]], base_report: dict[str, Any] | None = None) -> None:
    meta = schema_meta(BATCH_SCHEMA_VERSION)
    report: dict[str, Any] = dict(base_report) if isinstance(base_report, dict) else {}
    report["schema_version"] = meta["schema_version"]
    report["generated_at"] = meta["generated_at"]
    report["tool_version"] = meta["tool_version"]
    report["items"] = items
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_json_report(json_out: str | None, report: dict[str, Any]) -> None:
    if not json_out:
        return
    _write_batch_report(json_out, items=list(report.get("items", [])), base_report=report)


def _write_batch_status(batch_run_id: str, report: dict[str, Any]) -> None:
    p = Path("runs") / "_batch" / batch_run_id / "batch_status.json"
    _write_batch_report(p, items=list(report.get("items", [])), base_report=report)


def _write_report(report: dict[str, Any], report_out_path: str | None, batch_run_id: str) -> None:
    _write_batch_status(batch_run_id, report)
    # Also persist a stable batch_report.json alongside batch_status.json.
    p_report = Path("runs") / "_batch" / batch_run_id / "batch_report.json"
    _write_batch_report(p_report, items=list(report.get("items", [])), base_report=report)
    report["batch_report_path"] = str(p_report)
    _write_json_report(report_out_path, report)


def _batch_rc(items: list[dict[str, Any]]) -> int:
    # Batch policy v0.1: 0=all ok, 2=some item failures, 1=runner crash/usage.
    has_fail = any((i.get("result_rc") not in (None, RC_OK)) for i in items)
    return 2 if has_fail else RC_OK


def _exit_code_from_report(report: dict[str, Any]) -> int:
    summary = report.get("summary") or {}
    return _exit_code_from_summary(summary)


def _exit_code_from_summary(summary: dict[str, Any]) -> int:
    # 0: all ok (or ok+skipped)
    # 2: some failed but report produced
    # 1: runner crash (used only when we cannot produce a valid report)
    fail = int(summary.get("fail") or 0)
    return 2 if fail > 0 else 0


def _empty_item(job_path: str) -> dict[str, Any]:
    return {
        "job_path": job_path,
        "run_id": None,
        "result_rc": None,
        "cached": None,
        "cache_reason": None,
        "out_path": None,
        "output_path": None,
        "trace_path": None,
        "error_type": None,
        "job_hash": None,
        "engine_version": None,
    }


def _enforce_item_contract(item: dict[str, Any], *, engine_version: str, job_hash: str | None) -> dict[str, Any]:
    out = dict(item)
    out["job_path"] = out.get("job_path")
    out["run_id"] = out.get("run_id")
    out["result_rc"] = out.get("result_rc")
    out["cached"] = out.get("cached")
    out["cache_reason"] = out.get("cache_reason")
    out["out_path"] = out.get("out_path")
    out["error_type"] = out.get("error_type")
    out["job_hash"] = job_hash
    out["engine_version"] = engine_version
    return out


def _finalize_success(item: dict[str, Any], *, cached: bool, out_path: str | None, run_id: str | None) -> None:
    item["cached"] = cached
    item["out_path"] = out_path
    item["output_path"] = out_path
    item["run_id"] = run_id
    item["error_type"] = None
    item["result_rc"] = RC_OK


def _finalize_failure(item: dict[str, Any], e: Exception) -> None:
    et = classify_exception(e)
    if et == "unknown_error":
        et = "internal_error"
    item["error_type"] = et
    item["result_rc"] = rc_for_error_type(et)


def _main_impl(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    batch_run_id = _batch_run_id_now()
    batch_started_at = _utc_now_iso()
    batch_engine_version = _engine_version()
    t0 = time.time()
    args = _parse_args(argv)
    selection_mode = "all"
    source_jobset_path: str | None = None
    source_jobset_hash: str | None = None
    if args.jobset and args.only_failed_from:
        err = "--jobset cannot be combined with --only-failed-from"
        jobs, file_opts = [], {}
    elif args.jobset:
        jobs, source_jobset_hash, jobset_err = _jobs_from_jobset(args.jobset)
        err = jobset_err
        file_opts = {}
        if err is None:
            source_jobset_path = str(Path(args.jobset))
            selection_mode = "jobset"
    elif args.only_failed_from:
        jobs, err, file_opts = [], None, {}
    else:
        jobs, err, file_opts = _discover_jobs(args)
    # apply optional manifest defaults when CLI did not set an explicit override
    if not args.json_out and isinstance(file_opts.get("json_out"), str):
        args.json_out = str(file_opts["json_out"])
    if (not args.stop_on_error) and isinstance(file_opts.get("stop_on_error"), bool):
        args.stop_on_error = bool(file_opts["stop_on_error"])
    source_batch_report: str | None = None
    if args.only_failed_from:
        sel_jobs, sel_err = _jobs_from_failed_report(args.only_failed_from)
        if sel_err is not None:
            err = sel_err
        else:
            jobs = sel_jobs
            source_batch_report = str(Path(args.only_failed_from))
            selection_mode = "retry_failed_from" if bool(args.retry_failed) else "only_failed_from"
    elif args.retry_failed:
        err = "--retry-failed requires --only-failed-from <batch_report.json>"

    continue_on_error = bool(args.continue_on_error)
    if bool(args.stop_on_error):
        continue_on_error = False
    if args.max_fail is not None:
        if int(args.max_fail) < 1:
            err = "--max-fail must be >= 1"
        max_fail = int(args.max_fail)
    else:
        max_fail = 999999 if continue_on_error else 1

    if err is not None:
        t1 = time.time()
        batch_ended_at = _utc_now_iso()
        batch_duration_ms = _duration_ms(t0, t1)
        stdout_payload = _stdout_error_payload(
            error_type="usage",
            message="invalid arguments or job discovery failure",
            hint=str(err),
            exit_code=1,
        )
        report_meta = {
            "tool": "render_batch",
            "timestamp": batch_ended_at,
            "cwd": str(Path.cwd()),
            "args": args_list,
            "component": "layer2.cli.render_batch",
            "batch_run_id": batch_run_id,
            "git": _git_info(),
            "host": _host_info(),
        }
        report_summary = {
            "total": 0,
            "ok": 0,
            "fail": 0,
            "skipped": 0,
            "cached": 0,
            "cached_count": 0,
            "rendered_count": 0,
            "batch_ok": False,
            "stopped_early": False,
            "stop_reason": None,
            "continue_on_error": continue_on_error,
            "max_fail": int(max_fail),
            "selection_mode": selection_mode,
            "selected_jobs_count": 0,
            "jobset_path": source_jobset_path,
            "jobset_hash": source_jobset_hash,
            "retries_attempted": 0,
            "retries_succeeded": 0,
            "total_duration_ms": 0,
            "avg_duration_ms": 0,
            "max_duration_ms": 0,
            "duration_sec_total": 0.0,
            "duration_sec_p50": 0.0,
            "duration_sec_p95": 0.0,
        }
        report = _build_report(
            meta=report_meta,
            summary=report_summary,
            fail_by_type=_count_fail_by_type([]),
            sample_failures=[],
            items=[],
        )
        report["schema_version"] = "0.1"
        report["batch_run_id"] = batch_run_id
        report["engine_version"] = batch_engine_version
        report["started_at"] = batch_started_at
        report["ended_at"] = batch_ended_at
        report["jobs_count"] = 0
        report["ok_count"] = 0
        report["fail_count"] = 0
        report["batch_ok"] = False
        report["stopped_early"] = False
        report["stop_reason"] = None
        report["continue_on_error"] = continue_on_error
        report["max_fail"] = int(max_fail)
        report["selection_mode"] = selection_mode
        report["source_batch_report"] = source_batch_report
        report["selected_jobs_count"] = 0
        report["jobset_path"] = source_jobset_path
        report["jobset_hash"] = source_jobset_hash
        report["items"] = []
        _write_batch_status(batch_run_id, report)
        _write_json_report(args.json_out, report)
        _print_stdout_json(stdout_payload)
        return 1

    items: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    failed = 0
    succeeded = 0
    retries_attempted = 0
    retries_succeeded = 0
    duration_values: list[int] = []
    stopped_early = False
    stop_reason: str | None = None

    for idx, job_path in enumerate(jobs, start=1):
        item_t0 = time.time()
        item_started_at = _utc_now_iso()
        item = _empty_item(job_path)
        job_hash_v = _job_hash_from_job(job_path)
        item["job_id"] = f"job_{idx:03d}"
        item["started_at"] = item_started_at
        try:
            run_id = _derive_run_id_from_job(job_path)
            job_out_path = _job_output_path(job_path)
            status = _read_run_status(run_id)
            status_ok = bool(status.get("ok", False)) if isinstance(status, dict) else False

            should_skip = False
            if isinstance(status, dict) and status_ok and (args.skip_existing or args.resume):
                should_skip = True

            if should_skip:
                result_rc = 0
                out_path = status.get("out_path") if isinstance(status, dict) else None
                if not out_path:
                    out_path = job_out_path
                cached = True
                error_type = "none"
                item_message = None
                item["cache_reason"] = (
                    str(status.get("cache_reason"))
                    if isinstance(status, dict) and isinstance(status.get("cache_reason"), str)
                    else "meta+mp4 ok"
                )
                duration_ms_val = None
                if isinstance(status, dict):
                    _d = status.get("duration_ms")
                    if isinstance(_d, (int, float)):
                        duration_ms_val = int(_d)
                    arts = status.get("artifacts")
                    if isinstance(arts, dict):
                        tr = arts.get("trace")
                        if isinstance(tr, str) and tr.strip():
                            item["trace_path"] = tr.strip()
                parsed: dict[str, Any] = {
                    "run_id": run_id,
                    "out_path": out_path,
                    "cached": cached,
                    "result_rc": result_rc,
                }
                _finalize_success(item, cached=cached, out_path=out_path, run_id=run_id)
            else:
                retry_used = False
                attempts_left = max(0, int(args.retry_io))
                duration_ms_val = None
                item_message = None
                while True:
                    cmd = [sys.executable, "-m", _render_job_module_name(), "--job", job_path]
                    proc = subprocess.run(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    proc_rc = int(proc.returncode)
                    parsed = _parse_render_result(proc.stdout or "")
                    run_id = parsed.get("run_id") or run_id
                    status = _read_run_status(run_id)
                    result_rc = int(status.get("result_rc", proc_rc)) if isinstance(status, dict) else proc_rc
                    out_path = parsed.get("out_path")
                    if not out_path and isinstance(status, dict):
                        out_path = status.get("out_path")
                    cached = bool(parsed.get("cached", False))
                    if not cached and isinstance(status, dict):
                        cached = bool(status.get("cached", False))
                    if isinstance(status, dict):
                        cr = status.get("cache_reason")
                        if isinstance(cr, str) and cr.strip():
                            item["cache_reason"] = cr.strip()
                    error_type = (
                        str(status.get("error_type"))
                        if isinstance(status, dict) and status.get("error_type")
                        else _infer_error_type(proc.stdout or "", rc=result_rc)
                    )
                    item_message = (
                        str(status.get("message"))
                        if isinstance(status, dict) and status.get("message")
                        else None
                    )
                    error_type = _normalize_error_type(error_type, item_message)
                    duration_ms_val = None
                    if isinstance(status, dict):
                        _d = status.get("duration_ms")
                        if isinstance(_d, (int, float)):
                            duration_ms_val = int(_d)
                        arts = status.get("artifacts")
                        if isinstance(arts, dict):
                            tr = arts.get("trace")
                            if isinstance(tr, str) and tr.strip():
                                item["trace_path"] = tr.strip()
                    if _error_bucket(error_type) == "io_error" and attempts_left > 0:
                        retries_attempted += 1
                        retry_used = True
                        attempts_left -= 1
                        if int(args.retry_delay_ms) > 0:
                            time.sleep(int(args.retry_delay_ms) / 1000.0)
                        continue
                    if retry_used and result_rc == 0:
                        retries_succeeded += 1
                    break
                if result_rc == 0:
                    _finalize_success(item, cached=cached, out_path=out_path, run_id=run_id)
        except JobValidationError as e:
            run_id = item.get("run_id")
            result_rc = 2
            cached = False
            out_path = None
            error_type = "validation_error"
            item_message = str(e)
            parsed = {}
            duration_ms_val = None
            item["error_type"] = error_type
            item["result_rc"] = result_rc
        except Exception as e:
            run_id = item.get("run_id")
            result_rc = 1
            cached = False
            out_path = None
            error_type = "internal_error"
            item_message = str(e)
            parsed = {}
            duration_ms_val = None
            _finalize_failure(item, e)
            error_type = _normalize_error_type(str(item.get("error_type") or "internal_error"), item_message)
            result_rc = int(item.get("result_rc", 1))
        ok = result_rc == 0
        if ok:
            succeeded += 1
        else:
            failed += 1

        if item.get("run_id") is None:
            item["run_id"] = run_id
        _attach_run_refs(item, item.get("run_id"))
        if item.get("result_rc") is None:
            item["result_rc"] = result_rc
        if item.get("cached") is None:
            item["cached"] = cached
        if item.get("cache_reason") is None and bool(item.get("cached", False)):
            item["cache_reason"] = "meta+mp4 ok"
        if item.get("out_path") is None:
            item["out_path"] = out_path
        if item.get("output_path") is None:
            item["output_path"] = out_path
        if item.get("error_type") is None and result_rc != 0:
            item["error_type"] = _normalize_error_type(error_type, item_message)
        _attach_run_refs(item, item.get("run_id"))
        item["status"] = "ok" if result_rc == 0 else "fail"
        if bool(item.get("cached", False)) and result_rc == 0:
            item["status"] = "skipped"
        if isinstance(duration_ms_val, int) and duration_ms_val >= 0:
            item["duration_sec"] = round(duration_ms_val / 1000.0, 3)
        else:
            item["duration_sec"] = round(max(0.0, time.time() - item_t0), 3)
        item["ended_at"] = _utc_now_iso()
        if result_rc != 0:
            fail_item = _make_fail_item(
                job_path=str(item.get("job_path") or job_path),
                duration_sec=float(item.get("duration_sec") or 0.0),
                err_type=str(item.get("error_type")),
                message=item_message or "",
                run_id=(str(item.get("run_id")) if item.get("run_id") else None),
                trace_path=(str(item.get("trace_path")) if item.get("trace_path") else None),
                code=result_rc,
            )
            item["status"] = fail_item["status"]
            item["duration_sec"] = fail_item["duration_sec"]
            item["error"] = fail_item["error"]
        else:
            item["error"] = None
        item = _enforce_item_contract(item, engine_version=batch_engine_version, job_hash=job_hash_v)
        items.append(item)
        if isinstance(duration_ms_val, int) and duration_ms_val >= 0:
            duration_values.append(duration_ms_val)

        run_item: dict[str, Any] = {"job_path": job_path, "rc": result_rc, "ok": ok}
        run_item.update(parsed)
        run_item["error_type"] = error_type
        runs.append(run_item)
        if failed >= int(max_fail):
            stopped_early = True
            stop_reason = f"max_fail_reached:{int(max_fail)}"
            break
        if (not continue_on_error) and failed > 0:
            stopped_early = True
            stop_reason = "first_failure"
            break

    t1 = time.time()
    batch_ended_at = _utc_now_iso()
    batch_duration_ms = _duration_ms(t0, t1)
    total_duration_ms = int(sum(duration_values)) if duration_values else 0
    avg_duration_ms = int(round(total_duration_ms / len(duration_values))) if duration_values else 0
    max_duration_ms = int(max(duration_values)) if duration_values else 0
    min_duration_ms = int(min(duration_values)) if duration_values else 0
    fail_by_type = _count_fail_by_type(items)
    skipped = sum(1 for it in items if it.get("status") == "skipped")
    duration_secs = [float(it.get("duration_sec", 0.0) or 0.0) for it in items]
    duration_total = max(0.0, time.time() - t0)
    summary = {
        "total": len(items),
        "ok": sum(1 for it in items if it.get("status") == "ok"),
        "fail": sum(1 for it in items if it.get("status") == "fail"),
        "skipped": sum(1 for it in items if it.get("status") == "skipped"),
        "cached_count": sum(1 for it in items if bool(it.get("cached", False))),
        "rendered_count": sum(1 for it in items if not bool(it.get("cached", False))),
        "batch_ok": sum(1 for it in items if it.get("status") == "fail") == 0,
        "stopped_early": bool(stopped_early),
        "stop_reason": stop_reason,
        "continue_on_error": bool(continue_on_error),
        "max_fail": int(max_fail),
        "selection_mode": selection_mode,
        "selected_jobs_count": len(jobs),
        "jobset_path": source_jobset_path,
        "jobset_hash": source_jobset_hash,
        "duration_sec_total": float(duration_total),
    }
    summary_out = {
        "batch_id": batch_run_id,
        "started_at": batch_started_at,
        "ended_at": batch_ended_at,
        "ok": summary["fail"] == 0,
        "exit_code": _exit_code_from_summary(summary),
        "error": None,
        "contract_version": "1",
        "summary": summary,
        "fail_by_type": fail_by_type,
        "items": items,
        "runs": runs,
        "batch_ok": bool(summary["batch_ok"]),
        "stopped_early": bool(stopped_early),
        "stop_reason": stop_reason,
        "continue_on_error": bool(continue_on_error),
        "max_fail": int(max_fail),
        "selection_mode": selection_mode,
        "source_batch_report": source_batch_report,
        "selected_jobs_count": len(jobs),
        "jobset_path": source_jobset_path,
        "jobset_hash": source_jobset_hash,
    }
    report_meta = {
        "component": "layer2.cli.render_batch",
        "batch_run_id": batch_run_id,
        "tool": "render_batch",
        "timestamp": batch_ended_at,
        "cwd": str(Path.cwd()),
        "args": args_list,
        "git": _git_info(),
        "host": _host_info(),
    }
    sample_failures = _collect_sample_failures(items)
    report = _build_report(
        meta=report_meta,
        summary=summary,
        fail_by_type=fail_by_type,
        sample_failures=sample_failures,
        items=items,
    )
    report["schema_version"] = "0.1"
    report["batch_run_id"] = batch_run_id
    report["engine_version"] = batch_engine_version
    report["started_at"] = batch_started_at
    report["ended_at"] = batch_ended_at
    report["jobs_count"] = int(summary.get("total", 0))
    report["ok_count"] = int(summary.get("ok", 0))
    report["fail_count"] = int(summary.get("fail", 0))
    report["batch_ok"] = bool(summary.get("batch_ok", False))
    report["stopped_early"] = bool(stopped_early)
    report["stop_reason"] = stop_reason
    report["continue_on_error"] = bool(continue_on_error)
    report["max_fail"] = int(max_fail)
    report["selection_mode"] = selection_mode
    report["source_batch_report"] = source_batch_report
    report["selected_jobs_count"] = len(jobs)
    report["jobset_path"] = source_jobset_path
    report["jobset_hash"] = source_jobset_hash
    report["timing"] = {
        "total_duration_ms": int(total_duration_ms),
        "avg_duration_ms": int(avg_duration_ms) if duration_values else None,
        "max_duration_ms": int(max_duration_ms) if duration_values else None,
        "min_duration_ms": int(min_duration_ms) if duration_values else None,
    }
    slow = sorted(
        [
            {
                "job_path": it.get("job_path"),
                "run_id": it.get("run_id"),
                "render_duration_ms": int(round(float(it.get("duration_sec", 0.0) or 0.0) * 1000.0)),
                "cached": bool(it.get("cached", False)),
            }
            for it in items
        ],
        key=lambda x: int(x.get("render_duration_ms") or 0),
        reverse=True,
    )[:5]
    report["slowest"] = {"top_n": 5, "items": slow}
    report["items"] = [dict(it) for it in items]
    _write_report(report, args.json_out, batch_run_id)
    _print_stdout_json(summary_out)
    return int(summary_out["exit_code"])


def main(argv: list[str] | None = None) -> int:
    try:
        return _main_impl(argv)
    except SystemExit as e:
        raw_code = getattr(e, "code", 1)
        if raw_code is None:
            code = 1
        else:
            try:
                code = int(raw_code)
            except Exception:
                code = 1
        if code == 0:
            payload = _ok_payload_for_help(hint=None)
        else:
            payload = _stdout_error_payload(
                error_type="system_exit",
                message="SystemExit",
                hint="See stderr for details",
                exit_code=code,
            )
        _print_stdout_json(payload)
        return code
    except Exception as e:  # pragma: no cover
        traceback.print_exc(file=sys.stderr)
        payload = _stdout_error_payload(
            error_type="exception",
            message=str(e) if str(e) else e.__class__.__name__,
            hint="See stderr traceback",
            exit_code=1,
        )
        _print_stdout_json(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
