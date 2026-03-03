from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import hashlib
import time
import datetime as _dt
import shutil
import subprocess
from typing import Any, Dict, Optional


RUN_STORE_VERSION = "0.5"
CONTRACT_VERSION = "0.5"


# Single source of truth for canonical run-store artifacts.
# Output file name is variable (basename of requested output path), so mp4 is
# represented as a wildcard contract.
REQUIRED_ARTIFACTS = [
    "job.layer2.json",
    "job.layer1.json",
    "meta.json",
    "stdout.log",
    "*.mp4",
]

TRACE_CANDIDATE_GLOBS = [
    "*trace*",
    "stdout*",
    "stderr*",
    "*.log",
    "*_trace*",
]


def new_run_id() -> str:
    # V0.7: time-based; later we can switch to content-hash (deterministic).
    return time.strftime("%Y%m%d_%H%M%S")


@dataclass
class RunPaths:
    run_dir: Path
    layer2_job: Path
    layer1_job: Path
    meta: Path
    status: Path
    stdout: Path
    trace: Path
    out: Path

    @property
    def mp4(self) -> Path:
        # Canonical alias used by newer helpers/contracts.
        return self.out


def _stable_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_id_from_job(job: Dict[str, Any]) -> str:
    s = _stable_json(job).encode("utf-8")
    h = hashlib.sha256(s).hexdigest()
    return h[:12]


def prepare_run(root: Path, out_path: str, job: Optional[Dict[str, Any]] = None) -> RunPaths:
    run_id = run_id_from_job(job) if isinstance(job, dict) else new_run_id()
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_name = Path(out_path).name if out_path else "out.mp4"
    return RunPaths(
        run_dir=run_dir,
        layer2_job=run_dir / "job.layer2.json",
        layer1_job=run_dir / "job.layer1.json",
        meta=run_dir / "meta.json",
        status=run_dir / "status.json",
        stdout=run_dir / "stdout.log",
        trace=run_dir / "trace.txt",
        out=run_dir / out_name,
    )


def run_paths(run_dir: Path, mp4_rel: str | None = None) -> RunPaths:
    """
    Canonical run-dir layout helper for callers that already know run_dir.
    """
    out_name = mp4_rel or "output.mp4"
    return RunPaths(
        run_dir=run_dir,
        layer2_job=run_dir / "job.layer2.json",
        layer1_job=run_dir / "job.layer1.json",
        meta=run_dir / "meta.json",
        status=run_dir / "status.json",
        stdout=run_dir / "stdout.log",
        trace=run_dir / "trace.txt",
        out=run_dir / out_name,
    )


def write_json(p: Path, obj: Dict[str, Any]) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def status_started(run_id: str) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "state": "started",
        "rc": None,
        "artifacts_ok": False,
        "started_at": time.time(),
        "ended_at": None,
    }


def status_finished(base: dict[str, Any], rc: int, artifacts_ok: bool) -> dict[str, Any]:
    base = dict(base)
    base["rc"] = rc
    base["artifacts_ok"] = bool(artifacts_ok)
    base["ended_at"] = time.time()
    base["state"] = "succeeded" if (rc == 0 and artifacts_ok) else "failed"
    return base


def init_trace(trace_path: Path, header: str | None = None) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8", newline="\n") as f:
        ts = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        f.write(f"[{ts}] trace: start\n")
        if header:
            f.write(header.rstrip() + "\n")
        f.flush()


def _now_z() -> str:
    return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def file_bytes(p: Path) -> int:
    try:
        return p.stat().st_size
    except FileNotFoundError:
        return 0


def try_ffprobe_duration_sec(mp4_path: Path) -> float | None:
    # Portable: ffprobe may not be installed.
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(mp4_path),
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if not out:
            return None
        return float(out.splitlines()[0])
    except Exception:
        return None


def compute_artifacts_ok(mp4_path: Path) -> tuple[bool, dict[str, Any]]:
    b = file_bytes(mp4_path)
    info: dict[str, Any] = {"mp4_path": str(mp4_path), "mp4_bytes": b}

    if b <= 0:
        info["mp4_ok"] = False
        return False, info

    # Optional duration check via ffprobe
    dur = try_ffprobe_duration_sec(mp4_path)
    if dur is not None:
        info["mp4_duration_sec"] = dur
        if dur <= 0.1:
            info["mp4_ok"] = False
            info["mp4_note"] = "duration too small; possibly broken file"
            return False, info

    info["mp4_ok"] = True
    return True, info


def ensure_trace(trace_path: Path) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    if trace_path.exists():
        return
    trace_path.write_text(f"[{_now_z()}] trace: created (empty)\n", encoding="utf-8")


def discover_trace(run_dir: Path) -> Path | None:
    for g in TRACE_CANDIDATE_GLOBS:
        for p in run_dir.glob(g):
            if p.is_file():
                name = p.name.lower()
                if name == "trace.txt":
                    return p
                return p
    return None


def canonicalize_trace(run_dir: Path, canonical_trace: Path) -> dict[str, Any]:
    """
    Returns:
      - trace_found: bool
      - trace_source: str|None
      - trace_canonical: str
    """
    canonical_trace.parent.mkdir(parents=True, exist_ok=True)

    if canonical_trace.exists():
        return {
            "trace_found": True,
            "trace_source": str(canonical_trace),
            "trace_canonical": str(canonical_trace),
        }

    src = discover_trace(run_dir)
    if src and src.exists():
        shutil.copyfile(src, canonical_trace)
        txt = canonical_trace.read_text(encoding="utf-8", errors="replace")
        header = f"[{_now_z()}] trace: canonicalized from {src.name}\n"
        canonical_trace.write_text(header + txt, encoding="utf-8")
        return {
            "trace_found": True,
            "trace_source": str(src),
            "trace_canonical": str(canonical_trace),
        }

    ensure_trace(canonical_trace)
    return {
        "trace_found": False,
        "trace_source": None,
        "trace_canonical": str(canonical_trace),
    }


def check_required_artifacts(run_dir: Path, *, mp4_min_bytes: int = 1024) -> tuple[bool, list[str]]:
    """
    Returns (ok, missing).
    Checks REQUIRED_ARTIFACTS under run_dir (supports nested relative paths).
    For mp4 patterns, requires at least one file with size >= mp4_min_bytes.
    """
    missing: list[str] = []
    for rel in REQUIRED_ARTIFACTS:
        # Wildcard entries (e.g., *.mp4, artifacts/*.mp4)
        if any(ch in rel for ch in "*?[]"):
            matches = sorted(run_dir.glob(rel))
            if not matches:
                missing.append(rel)
                continue
            # Apply min-bytes guard for mp4 artifacts.
            if rel.lower().endswith(".mp4"):
                has_large_enough_mp4 = False
                for p in matches:
                    try:
                        if p.is_file() and p.stat().st_size >= mp4_min_bytes:
                            has_large_enough_mp4 = True
                            break
                    except Exception:
                        continue
                if not has_large_enough_mp4:
                    missing.append(f"{rel}(min_bytes={mp4_min_bytes})")
            continue

        # Plain relative path entry (supports nested paths).
        if not (run_dir / rel).exists():
            missing.append(rel)

    return (len(missing) == 0, missing)


def finalize_run(
    *,
    run_id: str,
    run_dir: Path,
    meta_path: Path,
    status_path: Path,
    trace_path: Path,
    mp4_path: Path,
    cmd: list[str] | str | None,
    cwd: Path | None,
    rc: int,
    started_at: float,
    diagnosis: str | None = None,
) -> dict[str, Any]:
    # 1) Trace canonicalization (or create an empty canonical trace).
    trace_info = canonicalize_trace(run_dir=run_dir, canonical_trace=trace_path)

    # 2) Artifacts health (mp4 existence/size + optional ffprobe duration).
    artifacts_ok, art_info = compute_artifacts_ok(mp4_path)

    # 3) Write status.
    ended_at = time.time()
    status = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "state": "succeeded" if (rc == 0 and artifacts_ok) else "failed",
        "rc": rc,
        "artifacts_ok": artifacts_ok,
        "started_at": started_at,
        "ended_at": ended_at,
    }
    write_json_atomic(status_path, status)

    # 4) Write meta.
    meta = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "rc": rc,
        "cwd": str(cwd) if cwd else None,
        "cmd": cmd,
        "diagnosis": diagnosis,
        "artifacts_ok": artifacts_ok,
        "trace_path": str(trace_path),
        **trace_info,
        **art_info,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_sec": round(ended_at - started_at, 3),
    }
    write_json_atomic(meta_path, meta)

    return {"status": status, "meta": meta}
