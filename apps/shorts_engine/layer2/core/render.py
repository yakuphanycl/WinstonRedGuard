from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .run_store import (
    RUN_STORE_VERSION,
    REQUIRED_ARTIFACTS,
    finalize_run,
    init_trace,
    prepare_run,
    status_started,
    write_json,
    write_json_atomic,
)

_META_HEAD_MAX_CHARS = 2000
MAX_TRACE_FALLBACK_BYTES = 64 * 1024  # 64KB


def _text_head(s: Optional[str], limit: int = _META_HEAD_MAX_CHARS) -> Optional[str]:
    """Return a safe trimmed head of text for meta.json."""
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n...[truncated to {limit} chars]"


def _run_cmd_capture(
    cmd: list[str],
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout_sec: Optional[int] = None,
) -> Tuple[int, str, str]:
    """Run subprocess and capture stdout/stderr text."""
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
        return int(p.returncode), p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return 124, out, (err + "\n[timeout]").strip()


def _build_meta_extra(engine_root: str, run_root: str, cwd: str, layer1_cmd: list[str]) -> dict[str, Any]:
    return {
        "engine_root": engine_root,
        "run_root": run_root,
        "cwd": cwd,
        "python": sys.executable,
        "platform": platform.platform(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "layer1_cmd": layer1_cmd,
    }


def _finalize_meta(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical meta merge: base + extra.
    Extra wins for fields it sets (so observability is never dropped).
    """
    m = dict(base)
    m.update(extra)
    return m


def _file_bytes(p: Path) -> Optional[int]:
    try:
        if p.exists() and p.is_file():
            return int(p.stat().st_size)
    except Exception:
        return None
    return None


def _safe_copy(src: Path, dst: Path) -> None:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception:
        # do not fail render just because debug copy failed
        pass


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _truncate_tail(text: str, max_bytes: int) -> str:
    """
    Keep the tail where the most valuable diagnostics usually are.
    """
    if max_bytes <= 0:
        return ""
    b = text.encode("utf-8", errors="replace")
    if len(b) <= max_bytes:
        return text
    tail = b[-max_bytes:]
    s = tail.decode("utf-8", errors="replace")
    return "[trace_fallback] NOTE: output truncated to last " + str(max_bytes) + " bytes\n" + s


def _write_trace_fallback(
    trace_path: Path,
    *,
    stdout_path: Path,
    stderr_path: Path,
    max_bytes: int = MAX_TRACE_FALLBACK_BYTES,
) -> None:
    """
    Deterministic fallback: synthesize trace.txt from captured Layer-1 stdout/stderr.
    """
    out = _safe_read_text(stdout_path) if stdout_path else ""
    err = _safe_read_text(stderr_path) if stderr_path else ""
    txt = (
        "[trace_fallback] BEGIN layer1 stdout\n"
        + (out or "")
        + "\n[trace_fallback] END layer1 stdout\n\n"
        + "[trace_fallback] BEGIN layer1 stderr\n"
        + (err or "")
        + "\n[trace_fallback] END layer1 stderr\n"
    )
    txt = _truncate_tail(txt, max_bytes=max_bytes)
    _safe_write_text(trace_path, txt)


def _find_best_match(run_dir: Path, patterns: list[str]) -> Optional[Path]:
    for pat in patterns:
        hits = list(run_dir.glob(pat))
        if hits:
            hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return hits[0]
    return None


def _canonicalize_run_artifacts(
    *,
    run_dir: Path,
    produced_mp4_path: Optional[Path],
    layer1_stdout: str,
    layer1_stderr: str,
) -> dict[str, Optional[str]]:
    """
    Best-effort canonicalization into run_dir:
    - layer1_stdout.txt / layer1_stderr.txt
    - video.mp4 (canonical copy)
    - trace.txt (best-effort mapping from legacy names)
    """
    out: dict[str, Optional[str]] = {
        "canonical_mp4": None,
        "canonical_trace": None,
        "stdout_path": None,
        "stderr_path": None,
        "layer1_stdout_path": None,
        "layer1_stderr_path": None,
        "source_mp4": None,
        "source_trace": None,
        "trace_fallback_used": None,
    }

    stdout_path = run_dir / "layer1_stdout.txt"
    stderr_path = run_dir / "layer1_stderr.txt"
    _safe_write_text(stdout_path, layer1_stdout or "")
    _safe_write_text(stderr_path, layer1_stderr or "")
    out["stdout_path"] = str(stdout_path)
    out["stderr_path"] = str(stderr_path)
    out["layer1_stdout_path"] = str(stdout_path)
    out["layer1_stderr_path"] = str(stderr_path)

    canonical_mp4 = run_dir / "video.mp4"
    if produced_mp4_path and produced_mp4_path.exists():
        _safe_copy(produced_mp4_path, canonical_mp4)
        if canonical_mp4.exists():
            out["canonical_mp4"] = str(canonical_mp4)
            out["source_mp4"] = str(produced_mp4_path)
    else:
        found_mp4 = _find_best_match(run_dir, patterns=["*.mp4", "**/*.mp4"])
        if found_mp4:
            _safe_copy(found_mp4, canonical_mp4)
            if canonical_mp4.exists():
                out["canonical_mp4"] = str(canonical_mp4)
                out["source_mp4"] = str(found_mp4)

    canonical_trace = run_dir / "trace.txt"
    found_trace = _find_best_match(
        run_dir,
        patterns=[
            "*trace*.txt",
            "*_trace*.txt",
            "*render_trace*.txt",
            "*ffmpeg*.log",
            "*stdout*.txt",
            "*stderr*.txt",
            "*log*.txt",
            "*.log",
            "*.txt",
        ],
    )
    if found_trace and found_trace.exists():
        _safe_copy(found_trace, canonical_trace)
        if canonical_trace.exists():
            out["canonical_trace"] = str(canonical_trace)
            out["source_trace"] = str(found_trace)
            out["trace_fallback_used"] = "false"
    else:
        _write_trace_fallback(
            canonical_trace,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            max_bytes=MAX_TRACE_FALLBACK_BYTES,
        )
        if canonical_trace.exists():
            out["canonical_trace"] = str(canonical_trace)
            out["source_trace"] = None
            out["trace_fallback_used"] = "true"

    return out


def _diagnose(rc: int, stdout: str, stderr: str) -> Optional[str]:
    """Deterministic, conservative failure diagnosis."""
    if rc == 0:
        return None

    blob = (stdout or "") + "\n" + (stderr or "")
    b = blob.lower()

    if "no module named" in b or "modulenotfounderror" in b:
        return "import_error"
    if "filenotfounderror" in b or "the system cannot find the path specified" in b:
        return "missing_file"
    if "permissionerror" in b or "access is denied" in b:
        return "permission_denied"
    if "jsondecodeerror" in b or ("expecting value" in b and "json" in b):
        return "job_parse_error"
    if "schema" in b and ("validation" in b or "invalid" in b):
        return "job_schema_error"
    if "ffmpeg" in b and ("error" in b or "invalid" in b or "failed" in b):
        return "ffmpeg_error"
    if "unknown encoder" in b or "unknown decoder" in b:
        return "ffmpeg_codec_error"
    return "layer1_failed"


def _find_shorts_engine_root() -> Path:
    """
    Find shorts_engine repo root.
    Priority:
      1) SHORTS_ENGINE_ROOT env
      2) Parent-walk from this file until a directory named 'shorts_engine'
    """
    env_root = os.environ.get("SHORTS_ENGINE_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if p.exists():
            return p

    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if parent.name == "shorts_engine":
            return parent

    raise RuntimeError("SHORTS_ENGINE_ROOT not found (env or parent-walk failed)")


def _layer2_to_layer1_job(j: Dict[str, Any]) -> Dict[str, Any]:
    script = None
    for k in ("script", "script_text", "text"):
        v = j.get(k)
        if isinstance(v, str) and v.strip():
            script = v.strip()
            break

    if script is None:
        subs = j.get("subtitles")
        if isinstance(subs, dict):
            items = subs.get("items")
            if isinstance(items, list):
                parts = []
                for it in items:
                    if isinstance(it, dict):
                        t = it.get("text")
                        if isinstance(t, str) and t.strip():
                            parts.append(t.strip())
                if parts:
                    script = " ".join(parts)

    if script is None:
        script = "V0: missing script text in Layer-2 job."

    out = j.get("output")
    out_path = "output/layer2_job.mp4"
    if isinstance(out, dict):
        p = out.get("path")
        if isinstance(p, str) and p.strip():
            out_path = p.strip()

    return {"script": script, "output": {"path": out_path}}


def build_layer1_job(j: Dict[str, Any]) -> Dict[str, Any]:
    return _layer2_to_layer1_job(j)


def render_from_job(j: Dict[str, Any], *, timeout_min: int = 30) -> Dict[str, Any]:
    """
    v0.7 core renderer:
    - Create runs/<run_id>/
    - Persist Layer-2 + Layer-1 jobs
    - Run layer1.cli.render_job and capture stdout/stderr to stdout.log
    - Write meta.json
    - Write trace.txt if failed
    - Rendered mp4 artifact is runs/<run_id>/out.mp4
    - Also copy to requested output path for compatibility
    """
    layer1_job = _layer2_to_layer1_job(j)
    out_path = layer1_job["output"]["path"]

    engine_root = _find_shorts_engine_root()
    repo_root = engine_root.parent
    runs_root = repo_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    rp = prepare_run(runs_root, out_path, j)
    init_trace(rp.trace, header=f"run_id={rp.run_dir.name}")
    started_at = time.time()
    write_json_atomic(rp.status, status_started(rp.run_dir.name))

    # --- CACHE HIT (v0.8.1) ---
    # If run output already exists, skip rendering and just ensure requested output.
    if (rp.run_dir / "video.mp4").exists():
        engine_root = _find_shorts_engine_root()
# (patched) duplicate removed: repo_root = engine_root.parent
        cached_cmd = [
            sys.executable,
            "-m",
            "shorts_engine.layer1.cli.render_job",
            "--job",
            str(rp.layer1_job.resolve()),
        ]
        meta_extra = _build_meta_extra(str(engine_root), str(runs_root.resolve()), str(repo_root), cached_cmd)
        requested = Path(out_path)
        try:
            requested.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if requested.resolve() != rp.out.resolve():
            try:
                requested.write_bytes(rp.out.read_bytes())
            except Exception:
                pass
        meta = {
            "run_id": rp.run_dir.name,
            "rc": 0,
            "cached": True,
            "requested_out": str(requested),
            "run_out": str(rp.out),
            "cwd": str(engine_root),
            "cmd": cached_cmd,
            "run_store_version": RUN_STORE_VERSION,
            "required_artifacts": REQUIRED_ARTIFACTS,
        }
        mp4_bytes = _file_bytes(rp.out)
        run_layer1_job = rp.run_dir / "layer1_job.json"
        _safe_copy(rp.layer1_job, run_layer1_job)
        meta_extra["layer1_job_path"] = str(run_layer1_job)
        meta["layer1_duration_ms"] = None
        meta["layer1_rc"] = None
        meta["layer1_stdout_head"] = None
        meta["layer1_stderr_head"] = None
        meta["diagnosis"] = None
        meta["artifacts_ok"] = bool(mp4_bytes and mp4_bytes > 0)
        meta["mp4_path"] = str(rp.out)
        meta["mp4_bytes"] = mp4_bytes
        meta["trace_path"] = str(rp.trace)
        meta["artifacts"] = {
            "mp4_path": str(rp.out),
            "mp4_bytes": mp4_bytes,
            "artifacts_ok": bool(mp4_bytes and mp4_bytes > 0),
            "cached": True,
        }
        canon = _canonicalize_run_artifacts(
            run_dir=rp.run_dir,
            produced_mp4_path=rp.out,
            layer1_stdout="",
            layer1_stderr="",
        )
        meta["canonical_mp4"] = canon.get("canonical_mp4")
        meta["canonical_trace"] = canon.get("canonical_trace")
        meta["layer1_stdout_path"] = canon.get("stdout_path")
        meta["layer1_stderr_path"] = canon.get("stderr_path")
        meta["source_mp4"] = canon.get("source_mp4")
        meta["source_trace"] = canon.get("source_trace")
        meta["trace_fallback_used"] = canon.get("trace_fallback_used")
        if isinstance(meta.get("artifacts"), dict):
            meta["artifacts"]["trace_fallback_used"] = canon.get("trace_fallback_used")
        mp4_for_contract = Path(canon["canonical_mp4"]) if canon.get("canonical_mp4") else rp.out
        trace_for_contract = Path(canon["canonical_trace"]) if canon.get("canonical_trace") else rp.trace
        fin = finalize_run(
            run_id=rp.run_dir.name,
            run_dir=rp.run_dir,
            meta_path=rp.meta,
            status_path=rp.status,
            trace_path=trace_for_contract,
            mp4_path=mp4_for_contract,
            cmd=cached_cmd,
            cwd=engine_root,
            rc=0,
            started_at=started_at,
            diagnosis=None,
        )
        # QC: audio stream must exist (v0)
        qc = _qc_check_audio_stream(rp.run_dir / "video.mp4")
        if not qc.get("ok", False):
            raise RuntimeError(qc.get("error", "qc_failed"))
        meta_contract = fin.get("meta", {})
        meta_rich = _finalize_meta(meta, meta_extra)
        merged = dict(meta_rich)
        merged.update(meta_contract)
        write_json_atomic(rp.meta, merged)
        return {
            "run_id": rp.run_dir.name,
            "rc": 0,
            "cached": True,
            "out_path": str(requested),
            "run_dir": str(rp.run_dir),
            "run_out": str(rp.out),
        }
    # --- END CACHE HIT ---

    write_json(rp.layer2_job, j)

    layer1_job_run = dict(layer1_job)
    layer1_job_run["output"] = {"path": str(rp.out.resolve())}
    write_json(rp.layer1_job, layer1_job_run)
    run_layer1_job = rp.run_dir / "layer1_job.json"
    _safe_copy(rp.layer1_job, run_layer1_job)

    engine_root = _find_shorts_engine_root()

# (patched) removed duplicate: repo_root = engine_root.parent
    cmd = [
        sys.executable,
        "-m",
        "shorts_engine.layer1.cli.render_job",
        "--job",
        str(rp.layer1_job.resolve()),
    ]
    meta_extra = _build_meta_extra(str(engine_root), str(runs_root.resolve()), str(repo_root), cmd)
    meta_extra["layer1_job_path"] = str(run_layer1_job)

    t0 = time.perf_counter()
    rc, out, err = _run_cmd_capture(
        cmd=cmd,
        cwd=str(repo_root),
        timeout_sec=60 * max(1, int(timeout_min)),
    )
    dur_ms = int((time.perf_counter() - t0) * 1000)
    try:
        rp.stdout.write_text(out or "", encoding="utf-8", errors="replace", newline="\n")
        (rp.run_dir / "stderr.log").write_text(err or "", encoding="utf-8", errors="replace", newline="\n")
    except Exception:
        pass
    canon = _canonicalize_run_artifacts(
        run_dir=rp.run_dir,
        produced_mp4_path=rp.out,
        layer1_stdout=out,
        layer1_stderr=err,
    )
    mp4_for_contract = Path(canon["canonical_mp4"]) if canon.get("canonical_mp4") else rp.out
    trace_for_contract = Path(canon["canonical_trace"]) if canon.get("canonical_trace") else rp.trace
    mp4_bytes = _file_bytes(rp.out)
    artifacts_ok = bool(mp4_bytes and mp4_bytes > 0)
    meta_extra["layer1_duration_ms"] = dur_ms
    meta_extra["layer1_rc"] = rc
    meta_extra["layer1_stdout_head"] = _text_head(out)
    meta_extra["layer1_stderr_head"] = _text_head(err)
    meta_extra["diagnosis"] = _diagnose(rc=rc, stdout=out, stderr=err)
    meta_extra["artifacts"] = {
        "mp4_path": str(rp.out),
        "mp4_bytes": mp4_bytes,
        "artifacts_ok": artifacts_ok,
        "cached": False,
    }
    meta_extra["canonical_mp4"] = canon.get("canonical_mp4")
    meta_extra["canonical_trace"] = canon.get("canonical_trace")
    meta_extra["layer1_stdout_path"] = canon.get("stdout_path")
    meta_extra["layer1_stderr_path"] = canon.get("stderr_path")
    meta_extra["source_mp4"] = canon.get("source_mp4")
    meta_extra["source_trace"] = canon.get("source_trace")
    meta_extra["trace_fallback_used"] = canon.get("trace_fallback_used")
    if isinstance(meta_extra.get("artifacts"), dict):
        meta_extra["artifacts"]["trace_fallback_used"] = canon.get("trace_fallback_used")

    requested = Path(out_path)
    try:
        requested.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    if rc == 0 and rp.out.exists():
        if requested.resolve() != rp.out.resolve():
            try:
                requested.write_bytes(rp.out.read_bytes())
            except Exception:
                pass
    else:
        try:
            rp.trace.write_text(f"layer1 returncode={rc}\n", encoding="utf-8")
        except Exception:
            pass

    meta = {
        "run_id": rp.run_dir.name,
        "rc": rc,
        "requested_out": str(requested),
        "run_out": str(rp.out),
        "cwd": str(engine_root),
        "cmd": cmd,
        "diagnosis": meta_extra.get("diagnosis"),
        "artifacts_ok": artifacts_ok,
        "mp4_path": str(rp.out),
        "mp4_bytes": mp4_bytes,
        "trace_path": str(rp.trace),
        "run_store_version": RUN_STORE_VERSION,
        "required_artifacts": REQUIRED_ARTIFACTS,
    }
    fin = finalize_run(
        run_id=rp.run_dir.name,
        run_dir=rp.run_dir,
        meta_path=rp.meta,
        status_path=rp.status,
        trace_path=trace_for_contract,
        mp4_path=mp4_for_contract,
        cmd=cmd,
        cwd=engine_root,
        rc=rc,
        started_at=started_at,
        diagnosis=meta_extra.get("diagnosis"),
    )
    meta_contract = fin.get("meta", {})
    meta_rich = _finalize_meta(meta, meta_extra)
    merged = dict(meta_rich)
    merged.update(meta_contract)
    write_json_atomic(rp.meta, merged)

    return {
        "run_id": rp.run_dir.name,
        "rc": rc,
        "out_path": str(requested),
        "run_dir": str(rp.run_dir),
        "run_out": str(rp.out),
        "stdout_path": str(rp.stdout),
    }




def _qc_check_audio_stream(mp4_path: Path) -> dict:
    # returns qc dict; raises RuntimeError if missing audio
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(mp4_path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return {"ok": False, "error": "ffprobe_failed", "stderr": (p.stderr or "")[:4000]}

    try:
        data = json.loads(p.stdout or "{}")
    except Exception as e:
        return {"ok": False, "error": "ffprobe_json_parse_failed", "message": str(e)}

    streams = data.get("streams") or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    qc = {"ok": True, "has_audio": has_audio}
    if not has_audio:
        qc["ok"] = False
        qc["error"] = "qc_audio_missing"
    return qc
