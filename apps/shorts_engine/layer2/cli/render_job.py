from pathlib import Path

fixed_path = Path("/mnt/data/render_job_fixed.py")
"""
Layer-2 CLI entrypoint (Golden Path).
- Load Layer-2 job json
- Create run dir under repo/runs/<run_id>
- Invoke Layer-1 renderer from repo root (correct module path)
- Optional: TTS mux + QC (PowerShell) if voice.mode == "tts"
- Verify artifacts (mp4/meta)
"""
from pathlib import Path
import sys
import json
import time
import uuid
import subprocess
from typing import Any, Dict, Tuple, Optional


def _die(msg: str, rc: int = 2) -> int:
    print(msg, file=sys.stderr)
    return rc


def _repo_root_from_this_file() -> Path:
    """
    Find repo root robustly by locating the 'shorts_engine' directory in parents,
    then returning its parent.
    """
    p = Path(__file__).resolve()
    for parent in [p.parent] + list(p.parents):
        if (parent / "shorts_engine").is_dir():
            return parent
    raise RuntimeError(f"repo root not found from: {p}")


def _new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _maybe_tts_mux(
    job: Dict[str, Any],
    repo: Path,
    run_dir: Path,
    out_mp4: Path,
    script_text: str,
    meta: Dict[str, Any],
) -> Tuple[int, Dict[str, Any]]:
    """
    Optional: TTS + MUX + QC (Golden path)
    Runs shorts_engine/tools/tts_mux_qc.ps1 and updates meta["artifacts"]["mp4_path"] if successful.

    Returns: (rc:int, meta:dict)
    """
    voice = job.get("voice") if isinstance(job.get("voice"), dict) else {}
    if voice.get("mode") != "tts":
        return 0, meta

    try:
        # If layer1 didn't produce the base mp4, there's nothing to mux.
        if not out_mp4.exists():
            meta["mux_rc"] = None
            meta["mux_error"] = "base mp4 missing; skip mux"
            (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0, meta

        tts_mux_ps1 = repo / "shorts_engine" / "tools" / "tts_mux_qc.ps1"
        if not tts_mux_ps1.exists():
            meta["mux_rc"] = 1
            meta["mux_error"] = f"tts mux script not found: {tts_mux_ps1}"
            (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1, meta

        # tts_mux_qc.ps1 expects: RunDir, InVideo, OutVideo, Text/TextFile (+ optional Voice/Rate/Volume/KeepTts)
        in_video_name = out_mp4.name  # usually "video.mp4"
        out_video_name = "final.mp4"

        # Write TTS text to file (UTF-8, no BOM) to avoid Windows/PS arg encoding issues
        tts_text_rel = "tts_text.txt"
        tts_text_path = run_dir / tts_text_rel
        try:
            tts_text_path.write_text(script_text, encoding="utf-8", newline="\n")
        except Exception:
            # If this fails, we'll fall back to -Text below (but we prefer TextFile)
            tts_text_rel = None


        mux_cmd = [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tts_mux_ps1),
            "-RunDir",
            str(run_dir),
            "-InVideo",
            in_video_name,
            "-OutVideo",
            out_video_name,
        ]

        # Add TTS text arg (prefer file; fallback to inline text)
        if tts_text_rel:
            mux_cmd += ["-TextFile", tts_text_rel]
        else:
            mux_cmd += ["-Text", script_text]


        # Optional voice mapping from job.voice
        # Example job.voice: {"mode":"tts","engine":"edge","voice":"tr-TR-EmelNeural","rate":"-5%","volume":"+0%","keep_tts":true}
        if isinstance(voice.get("voice"), str) and voice["voice"].strip():
            mux_cmd += ["-Voice", voice["voice"].strip()]
        if isinstance(voice.get("rate"), str) and voice["rate"].strip():
            mux_cmd += ["-Rate", voice["rate"].strip()]
        if isinstance(voice.get("volume"), str) and voice["volume"].strip():
            mux_cmd += ["-Volume", voice["volume"].strip()]
        if voice.get("keep_tts") is True:
            mux_cmd += ["-KeepTts"]

        print(f"[L2] mux_cmd={' '.join(mux_cmd)}")

        m = subprocess.run(
            mux_cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        (run_dir / "mux.stdout.txt").write_text(m.stdout or "", encoding="utf-8")
        (run_dir / "mux.stderr.txt").write_text(m.stderr or "", encoding="utf-8")
        meta["mux_rc"] = m.returncode

        if m.returncode != 0:
            if m.stderr:
                print((m.stderr or "").rstrip(), file=sys.stderr)
            (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return m.returncode, meta

        # Script may output one of these
        final_mp4 = run_dir / "final.mp4"
        with_audio = run_dir / "video_with_audio.mp4"

        chosen: Optional[Path] = None
        if final_mp4.exists():
            chosen = final_mp4
            meta.setdefault("artifacts", {})
            meta["artifacts"]["final_mp4"] = str(final_mp4)
        elif with_audio.exists():
            chosen = with_audio
            meta.setdefault("artifacts", {})
            meta["artifacts"]["video_with_audio"] = str(with_audio)

        if chosen is None:
            meta["mux_rc"] = 1
            meta["mux_error"] = "mux ok but no output mp4 found (final.mp4 / video_with_audio.mp4)"
            (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1, meta

        # Make artifacts.mp4_path point to the final chosen output
        meta.setdefault("artifacts", {})
        meta["artifacts"]["mp4_path"] = str(chosen)

        (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0, meta

    except Exception as e:
        meta["mux_rc"] = 1
        meta["mux_error"] = f"exception: {e}"
        (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1, meta


def _write_status(run_dir: Path, *, ok: bool, rc: int, out_path: str | None, run_id: str, cached: bool = False,
                  cache_reason: str | None = None, error_type: str | None = None, message: str | None = None,
                  duration_ms: int | None = None) -> None:
    """
    Writes runs/<run_id>/status.json for batch runner resume/skip logic.
    """
    status = {
        "ok": bool(ok),
        "result_rc": int(rc),
        "out_path": out_path,
        "run_id": run_id,
        "cached": bool(cached),
        "cache_reason": cache_reason,
        "error_type": error_type,
        "message": message,
        "duration_ms": duration_ms,
        "artifacts": {
            "trace": str(run_dir / "trace.txt"),
        },
    }
    (run_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_result_line(*, ok: bool, rc: int, out_path: str | None, run_id: str, cached: bool = False) -> None:
    """
    Prints a RESULT line that render_batch can parse.
    Expected format:
      RESULT ok rc=0 out=... run_id=... cached=True|False
    """
    outv = out_path if out_path else "none"
    tag = "ok" if ok else "fail"
    print(f"RESULT {tag} rc={int(rc)} out={outv} run_id={run_id} cached={bool(cached)}")

def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    # Accept both:
    #   render_job.py <job.json>
    #   render_job.py --job <job.json>
    if "--job" in argv:
        j = argv.index("--job")
        if j + 1 >= len(argv):
            return _die("missing value for --job")
        job_arg = argv[j + 1]
        # remove --job and its value so it won't trip unknown-arg parsing later
        argv = argv[:j] + argv[j + 2:]
        # put job path into argv[0]
        if not argv:
            argv = [job_arg]
        else:
            argv[0] = job_arg


    if not argv:
        return _die("usage: render_job.py <job.json> [--run-id <id>] [--job <job.json>] [--job <job.json>]")

    job_path = Path(argv[0]).resolve()
    run_id: Optional[str] = None

    # simple arg parse
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--run-id" and i + 1 < len(argv):
            run_id = argv[i + 1]
            i += 2
            continue
        return _die(f"unknown arg: {a}")

    run_id = run_id or _new_run_id()

    if not job_path.exists():
        return _die(f"job not found: {job_path}")

    try:
        job = json.loads(job_path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return _die(f"invalid job json: {e}")

    repo = _repo_root_from_this_file()
    runs_dir = repo / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Prepare Layer-1 input job under run_dir (Layer-1 schema minimal)
    # We assume Layer-1 reads a json job with "script" and "output.path"
    script_text = str(job.get("script") or job.get("hook") or "TEST")
    out_mp4 = run_dir / "video.mp4"

    layer1_job = {
        "script": script_text,
        "output": {"path": str(out_mp4)},
    }
    layer1_job_path = run_dir / "layer1_job.json"
    layer1_job_path.write_text(json.dumps(layer1_job, ensure_ascii=False, indent=2), encoding="utf-8")

    # Call Layer-1 from repo root to avoid module path/cwd bugs
    cmd = [
        sys.executable,
        "-m",
        "shorts_engine.layer1.cli.render_job",
        str(layer1_job_path),
    ]

    t0 = time.time()
    print(f"[L2] repo={repo}")
    print(f"[L2] run_id={run_id}")
    print(f"[L2] run_dir={run_dir}")
    print(f"[L2] cmd={' '.join(cmd)}")

    p = subprocess.run(
        cmd,
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    dt = time.time() - t0

    # Save logs
    (run_dir / "layer1.stdout.txt").write_text(p.stdout or "", encoding="utf-8")
    (run_dir / "layer1.stderr.txt").write_text(p.stderr or "", encoding="utf-8")

    print(f"[L2] layer1_rc={p.returncode} elapsed={dt:.2f}s")
    if p.stdout:
        print("[L2] --- layer1 stdout ---")
        print(p.stdout.rstrip())
    if p.stderr:
        print("[L2] --- layer1 stderr ---", file=sys.stderr)
        print(p.stderr.rstrip(), file=sys.stderr)

    # Minimal meta (always write, even if layer1 fails)
    meta: Dict[str, Any] = {
        "run_id": run_id,
        "repo": str(repo),
        "cwd": str(repo),
        "layer1_rc": p.returncode,
        "requested_job": str(job_path),
        "layer1_job": str(layer1_job_path),
        "artifacts": {
            "mp4_path": str(out_mp4) if out_mp4.exists() else None,
            "base_mp4": str(out_mp4),
        },
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Optional: run TTS mux/qc if voice.mode == "tts"
    rc_mux, meta = _maybe_tts_mux(job, repo, run_dir, out_mp4, script_text, meta)
    if rc_mux != 0:
        # Batch contract: status.json + RESULT line
        outp = (meta.get("artifacts") or {}).get("mp4_path")
        _write_status(run_dir, ok=False, rc=int(rc_mux), out_path=outp, run_id=run_id,
                      cached=False, error_type="render_error", message="mux failed")
        _print_result_line(ok=False, rc=int(rc_mux), out_path=outp, run_id=run_id, cached=False)
        return int(rc_mux)
    # Verify artifacts
    if p.returncode != 0:
        outp = (meta.get("artifacts") or {}).get("mp4_path")
        _write_status(run_dir, ok=False, rc=int(p.returncode), out_path=outp, run_id=run_id,
                      cached=False, error_type="render_error", message="layer1 failed")
        _print_result_line(ok=False, rc=int(p.returncode), out_path=outp, run_id=run_id, cached=False)
        return 1
    mp4_path = meta.get("artifacts", {}).get("mp4_path")
    if not mp4_path:
        return _die("FAIL: no mp4_path in meta artifacts", 1)
    if not Path(mp4_path).exists():
        return _die(f"FAIL: mp4 missing: {mp4_path}", 1)
    print("[L2] OK: mp4 produced")
    # Batch contract: status.json + RESULT line
    outp = (meta.get("artifacts") or {}).get("mp4_path")
    _write_status(run_dir, ok=True, rc=0, out_path=outp, run_id=run_id,
                  cached=False, error_type=None, message=None)
    _print_result_line(ok=True, rc=0, out_path=outp, run_id=run_id, cached=False)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())











