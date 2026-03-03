from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EXIT_USAGE = 2


def _eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def _read_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _norm_out(job: dict[str, Any]) -> str | None:
    out = job.get("output")
    if isinstance(out, str) and out.strip():
        return out.strip()
    if isinstance(out, dict):
        p = out.get("path")
        if isinstance(p, str) and p.strip():
            return p.strip()
    return None


def _norm_script(job: dict[str, Any]) -> str:
    s = job.get("script")
    if isinstance(s, str) and s.strip():
        return s.strip()
    if isinstance(s, dict):
        t = s.get("text")
        if isinstance(t, str) and t.strip():
            return t.strip()
    # fallback: subtitles.items
    subs = job.get("subtitles")
    if isinstance(subs, dict):
        items = subs.get("items")
        if isinstance(items, list):
            parts = []
            for it in items:
                if isinstance(it, dict):
                    tx = it.get("text")
                    if isinstance(tx, str) and tx.strip():
                        parts.append(tx.strip())
            if parts:
                return " ".join(parts)
    return " "


def _norm_duration(job: dict[str, Any]) -> float:
    # try layer2 style
    vid = job.get("video")
    if isinstance(vid, dict):
        d = vid.get("duration_sec")
        if isinstance(d, (int, float)) and float(d) > 0:
            return float(d)
    # fallback
    return 8.0


def _norm_res(job: dict[str, Any]) -> tuple[int, int]:
    vid = job.get("video")
    if isinstance(vid, dict):
        r = vid.get("resolution")
        if isinstance(r, str) and "x" in r:
            a, b = r.lower().split("x", 1)
            try:
                return int(a), int(b)
            except Exception:
                pass
    return 1080, 1920


def _norm_fps(job: dict[str, Any]) -> int:
    vid = job.get("video")
    if isinstance(vid, dict):
        fps = vid.get("fps")
        if isinstance(fps, int) and 0 < fps <= 240:
            return fps
    return 30
def _ff_escape_drawtext(s: str) -> str:
    """
    Escape text for ffmpeg drawtext. Critical: commas and colons break filtergraphs.
    """
    if s is None:
        return ""
    # ffmpeg drawtext escaping rules (good-enough set for our use):
    # \  -> \\
    # :  -> \:
    # ,  -> \,
    # '  -> \'
    # [ ] -> \[ \]
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("'", "\\'")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )

def _render_minimal(out_path: Path, text: str, w: int, h: int, fps: int, dur: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Extremely simple renderer: solid background + centered text.
    # Requires ffmpeg in PATH.
    draw = (
        "drawtext="
        "fontcolor=white:fontsize=48:"
        "x=(w-text_w)/2:y=(h-text_h)/2:"
        "text=" + text.replace(":", "\\:").replace(",", "\\,").replace("'", "\\'")
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={w}x{h}:r={fps}",
        "-t", f"{dur:.3f}",
        "-vf", draw,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]

    # keep stderr for debuggability
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + (p.stderr or "").strip())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    ap = argparse.ArgumentParser(prog="python -m layer1.cli.render_job")
    ap.add_argument("--job", dest="job", help="Path to job JSON")
    ap.add_argument("positional", nargs="?", help="Path to job JSON (positional)")
    ns = ap.parse_args(argv)

    job_path = ns.job or ns.positional
    if not job_path:
        _eprint("Usage: python -m layer1.cli.render_job --job <job.json>  OR  <job.json>")
        return EXIT_USAGE

    p = Path(job_path)
    if not p.exists():
        _eprint(f"Job file not found: {p}")
        return EXIT_USAGE

    job = _read_json(p)
    if not isinstance(job, dict):
        _eprint("JOB INVALID: root must be an object")
        return EXIT_USAGE

    out = _norm_out(job)
    if not out:
        _eprint("JOB INVALID: missing output.path")
        return EXIT_USAGE

    script = _norm_script(job)
    dur = _norm_duration(job)
    w, h = _norm_res(job)
    fps = _norm_fps(job)

    _render_minimal(Path(out), script, w, h, fps, dur)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




