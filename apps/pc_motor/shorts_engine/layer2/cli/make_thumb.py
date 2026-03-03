from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..core.version import __version__


def _repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[3]


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


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_size(s: str) -> tuple[int, int]:
    if "x" not in s:
        raise ValueError("size must be WxH")
    a, b = s.lower().split("x", 1)
    w, h = int(a), int(b)
    if w < 16 or h < 16:
        raise ValueError("size must be >=16x16")
    return w, h


def _find_run_dir(run_id: str, repo_root: Path) -> Path | None:
    for runs_dir in _candidate_runs_dirs(repo_root):
        p = runs_dir / run_id
        if p.exists() and p.is_dir():
            return p
    return None


def _resolve_possible_path(raw: str, *, run_dir: Path | None, repo_root: Path) -> Path:
    p = Path(raw.strip())
    if p.is_absolute():
        return p
    candidates: list[Path] = []
    if run_dir is not None:
        candidates.append((run_dir / p).resolve())
    candidates.append((repo_root / p).resolve())
    candidates.append((repo_root / "shorts_engine" / p).resolve())
    candidates.append((Path.cwd() / p).resolve())
    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if candidates else p.resolve()


def _default_out_path(run_id: str | None, mp4_path: Path | None) -> Path:
    if run_id:
        rr = _find_run_dir(run_id, _repo_root_from_file())
        if rr is not None:
            return rr / "thumb.png"
    if mp4_path is not None:
        return mp4_path.with_suffix(".thumb.png")
    return Path("thumb.png")


def _extract_frame(*, mp4: Path, out: Path, sec: float, size: tuple[int, int]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")
    w, h = size
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(float(sec)),
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        "-vf",
        vf,
        str(out),
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extract failed rc={p.returncode}")


def _make_gradient_text(*, out: Path, size: tuple[int, int], text: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as e:
        raise RuntimeError(f"Pillow is required for gradient_text mode: {e}") from e

    w, h = size
    img = Image.new("RGB", (w, h), (20, 30, 50))
    dr = ImageDraw.Draw(img)
    # deterministic simple vertical gradient
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(20 + 80 * t)
        g = int(30 + 40 * t)
        b = int(60 + 120 * t)
        dr.line([(0, y), (w, y)], fill=(r, g, b))

    txt = (text or "").strip().replace("\r", " ").replace("\n", " ")
    if not txt:
        txt = "Short"
    txt = " ".join(txt.split())
    max_chars = 70
    if len(txt) > max_chars:
        txt = txt[: max_chars - 1].rstrip() + "…"
    words = txt.split(" ")
    mid = max(1, len(words) // 2)
    line1 = " ".join(words[:mid]).strip()
    line2 = " ".join(words[mid:]).strip()
    lines = [line1] if not line2 else [line1, line2]

    font = ImageFont.load_default()
    y = int(h * 0.62)
    for line in lines:
        tw = int(dr.textlength(line, font=font))
        x = max(20, (w - tw) // 2)
        # shadow
        dr.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        dr.text((x, y), line, font=font, fill=(255, 255, 255))
        y += 20
    img.save(out, format="PNG")


def _derive_text_from_meta(run_dir: Path, meta: dict[str, Any]) -> str:
    jp = meta.get("job_path")
    if isinstance(jp, str) and jp.strip():
        p = Path(jp.strip())
        if not p.is_absolute():
            p = (run_dir / p).resolve()
        if p.exists():
            j = _load_json(p)
            if isinstance(j, dict):
                for key in ("hook", "title"):
                    v = j.get(key)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                subs = j.get("subtitles")
                if isinstance(subs, dict):
                    items = subs.get("items")
                    if isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict):
                                tx = it.get("text")
                                if isinstance(tx, str) and tx.strip():
                                    return tx.strip()
    return "Short video"


def _update_meta_thumb(run_dir: Path, *, thumb_path: Path, thumb_ok: bool) -> None:
    meta_path = run_dir / "meta.json"
    meta = _load_json(meta_path) or {}
    arts = meta.get("artifacts")
    if not isinstance(arts, dict):
        arts = {}
    arts["thumb_path"] = str(thumb_path).replace("\\", "/")
    arts["thumb_bytes"] = int(thumb_path.stat().st_size) if thumb_path.exists() else None
    arts["thumb_ok"] = bool(thumb_ok)
    meta["artifacts"] = arts
    _write_json(meta_path, meta)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.make_thumb")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--run-id", dest="run_id")
    p.add_argument("--mp4", dest="mp4")
    p.add_argument("--repo-root", dest="repo_root")
    p.add_argument("--mode", dest="mode", default="gradient_text", choices=["gradient_text", "frame"])
    p.add_argument("--size", dest="size", default="1280x720")
    p.add_argument("--text", dest="text")
    p.add_argument("--out", dest="out")
    p.add_argument("--sec", dest="sec", type=float, default=1.0)
    p.add_argument("--force", dest="force", action="store_true")
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        if not args.run_id and not args.mp4:
            print("ERROR: provide --run-id or --mp4")
            return 2
        repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root_from_file()
        size = _parse_size(args.size)

        run_dir: Path | None = None
        run_id: str | None = None
        mp4_path: Path | None = None
        meta: dict[str, Any] = {}

        if args.run_id:
            run_id = str(args.run_id).strip()
            run_dir = _find_run_dir(run_id, repo_root)
            if run_dir is None:
                print(f"ERROR: run-id not found: {run_id}")
                return 2
            meta = _load_json(run_dir / "meta.json") or {}
            arts = meta.get("artifacts")
            if isinstance(arts, dict):
                mp4v = arts.get("mp4_path")
                if isinstance(mp4v, str) and mp4v.strip():
                    mp4_path = _resolve_possible_path(mp4v, run_dir=run_dir, repo_root=repo_root)
            if mp4_path is None or (not mp4_path.exists()):
                for k in ("out_path", "output_path", "mp4_path"):
                    v = meta.get(k)
                    if isinstance(v, str) and v.strip():
                        p = _resolve_possible_path(v, run_dir=run_dir, repo_root=repo_root)
                        if p.exists():
                            mp4_path = p
                            break
        if args.mp4:
            p = Path(args.mp4)
            if not p.is_absolute():
                p = p.resolve()
            mp4_path = p
        if mp4_path is None or not mp4_path.exists():
            print("ERROR: mp4 path not found")
            return 2

        out_path = Path(args.out) if args.out else _default_out_path(run_id, mp4_path)
        if not out_path.is_absolute():
            out_path = out_path.resolve()
        if out_path.exists() and (not args.force):
            tb = int(out_path.stat().st_size)
            if run_dir is not None:
                _update_meta_thumb(run_dir, thumb_path=out_path, thumb_ok=True)
            print(f"make_thumb: exists, skipped out={out_path}")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "exit_code": 0,
                        "run_id": run_id,
                        "out_path": str(out_path),
                        "thumb_bytes": tb,
                        "mode": args.mode,
                        "size": args.size,
                        "cached": True,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        text = str(args.text).strip() if isinstance(args.text, str) else ""
        if not text and run_dir is not None:
            text = _derive_text_from_meta(run_dir, meta)
        if not text:
            text = "Short video"

        if not args.dry_run:
            if out_path.parent and str(out_path.parent) not in ("", "."):
                out_path.parent.mkdir(parents=True, exist_ok=True)
            if args.mode == "frame":
                _extract_frame(mp4=mp4_path, out=out_path, sec=float(args.sec), size=size)
            else:
                _make_gradient_text(out=out_path, size=size, text=text)

        thumb_ok = out_path.exists() and out_path.is_file() and out_path.stat().st_size > 0
        tb = int(out_path.stat().st_size) if thumb_ok else None
        if run_dir is not None and thumb_ok:
            _update_meta_thumb(run_dir, thumb_path=out_path, thumb_ok=True)

        print(
            f"make_thumb: ok={thumb_ok} mode={args.mode} size={args.size} out={out_path} "
            f"bytes={tb if tb is not None else 0}"
        )
        print(
            json.dumps(
                {
                    "ok": bool(thumb_ok),
                    "exit_code": 0 if thumb_ok else 2,
                    "run_id": run_id,
                    "out_path": str(out_path),
                    "thumb_bytes": tb,
                    "mode": args.mode,
                    "size": args.size,
                },
                ensure_ascii=False,
            )
        )
        return 0 if thumb_ok else 2
    except ValueError as e:
        print(f"ERROR: {e}")
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
