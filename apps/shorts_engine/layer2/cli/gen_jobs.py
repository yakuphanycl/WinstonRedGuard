from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.version import __version__


GENERATOR_VERSION = "0.1"
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha1_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _sha1_file(path: Path) -> str:
    return _sha1_text(path.read_text(encoding="utf-8-sig"))


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _job_hash(job_obj: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(job_obj).encode("utf-8")).hexdigest()


def _norm_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _write_text_utf8(path: Path, text: str) -> None:
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse_csv(path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned: dict[str, str] = {}
            for k, v in (row or {}).items():
                key = str(k or "").strip()
                if not key:
                    continue
                cleaned[key] = str(v or "").strip()
            if cleaned:
                out.append(cleaned)
    return out


def _sanitize_key(v: str) -> str:
    s = (v or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    if not s:
        s = "row"
    return s[:64]


def _row_key(row: dict[str, str]) -> str:
    src_id = row.get("id", "")
    if src_id.strip():
        return _sanitize_key(src_id)
    base = "|".join([row.get("hook", ""), row.get("body", ""), row.get("ending", "")])
    return _sha1_text(base)[:12]


def _replace_placeholders_in_string(s: str, row: dict[str, str], *, strict: bool) -> str:
    missing: list[str] = []

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in row:
            return str(row.get(key, ""))
        missing.append(key)
        return ""

    out = PLACEHOLDER_RE.sub(repl, s)
    if strict and missing:
        keys = ",".join(sorted(set(missing)))
        raise ValueError(f"missing placeholders: {keys}")
    return out


def _apply_template(value: Any, row: dict[str, str], *, strict: bool) -> Any:
    if isinstance(value, str):
        return _replace_placeholders_in_string(value, row, strict=strict)
    if isinstance(value, list):
        return [_apply_template(v, row, strict=strict) for v in value]
    if isinstance(value, dict):
        return {k: _apply_template(v, row, strict=strict) for k, v in value.items()}
    return value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.gen_jobs")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--input", dest="input_path", required=True, help="input CSV path")
    p.add_argument("--template", dest="template_path", required=True, help="template job json path")
    p.add_argument("--out-dir", dest="out_dir", required=True, help="output jobs dir")
    p.add_argument("--prefix", dest="prefix", default="job", help="job file prefix")
    p.add_argument("--start-index", dest="start_index", type=int, default=1, help="start index (default: 1)")
    p.add_argument("--limit", dest="limit", type=int, help="optional row limit")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="do not write job files")
    p.add_argument("--strict-template", dest="strict_template", action="store_true", help="error on unknown placeholders")
    p.add_argument("--overwrite", dest="overwrite", action="store_true", help="overwrite existing job files")
    p.add_argument("--manifest-out", dest="manifest_out", help="manifest output path")
    p.add_argument("--jobs-file-out", dest="jobs_file_out", help="jobs list output path")
    p.add_argument("--normalize-eol", dest="normalize_eol", action="store_true", default=True, help="write UTF-8 with normalized LF")
    return p.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> str | None:
    if int(args.start_index) < 1:
        return "--start-index must be >= 1"
    if args.limit is not None and int(args.limit) < 1:
        return "--limit must be >= 1"
    return None


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        err = _validate_args(args)
        if err is not None:
            print(f"ERROR: {err}")
            return 2

        input_path = Path(args.input_path)
        template_path = Path(args.template_path)
        out_dir = Path(args.out_dir)
        if not input_path.exists():
            print(f"ERROR: input not found: {input_path}")
            return 2
        if not template_path.exists():
            print(f"ERROR: template not found: {template_path}")
            return 2

        try:
            rows = _parse_csv(input_path)
        except Exception as e:
            print(f"ERROR: failed to parse csv: {e}")
            return 2
        template_obj = _read_json(template_path)
        if not isinstance(template_obj, dict):
            print("ERROR: template root must be object")
            return 2

        rows_sorted = sorted(rows, key=lambda r: _row_key(r))
        if args.limit is not None:
            rows_sorted = rows_sorted[: int(args.limit)]

        items: list[dict[str, Any]] = []
        jobs_list: list[str] = []
        emitted = 0
        skipped = 0
        errors = 0

        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        idx = int(args.start_index)
        for row in rows_sorted:
            rk = _row_key(row)
            source_id = row.get("id") or None
            filename = f"{args.prefix}_{idx:04d}_{rk}.json"
            idx += 1
            job_path = out_dir / filename
            tags_raw = row.get("tags", "")
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if isinstance(tags_raw, str) else []

            try:
                rendered = _apply_template(template_obj, row, strict=bool(args.strict_template))
                if not isinstance(rendered, dict):
                    raise ValueError("rendered template is not object")
                dur_v = row.get("duration_sec")
                if isinstance(dur_v, str) and dur_v.strip():
                    try:
                        dur_i = int(float(dur_v))
                    except Exception:
                        dur_i = None
                else:
                    dur_i = None
                if dur_i is not None:
                    video = rendered.get("video")
                    if not isinstance(video, dict):
                        video = {}
                        rendered["video"] = video
                    video["duration_sec"] = dur_i
                jh = _job_hash(rendered)

                if job_path.exists() and (not bool(args.overwrite)):
                    skipped += 1
                else:
                    if not args.dry_run:
                        _write_text_utf8(job_path, json.dumps(rendered, ensure_ascii=False, indent=2) + "\n")
                    emitted += 1

                item = {
                    "row_key": rk,
                    "source_id": source_id,
                    "job_path": _norm_path(job_path),
                    "job_hash": jh,
                    "duration_sec": dur_i,
                    "tags": tags,
                }
                items.append(item)
                jobs_list.append(_norm_path(job_path))
            except Exception:
                errors += 1
                if args.strict_template:
                    print("ERROR: strict-template failed during rendering")
                    return 2
                continue

        manifest_out = Path(args.manifest_out) if args.manifest_out else (out_dir / "manifest.json")
        jobs_file_out = Path(args.jobs_file_out) if args.jobs_file_out else (out_dir / "jobs.txt")
        payload: dict[str, Any] = {
            "schema_version": "0.1",
            "created_at": _iso_now(),
            "input_path": _norm_path(input_path),
            "template_path": _norm_path(template_path),
            "out_dir": _norm_path(out_dir),
            "generator_version": GENERATOR_VERSION,
            "policy": {
                "prefix": str(args.prefix),
                "limit": int(args.limit) if args.limit is not None else None,
                "strict_template": bool(args.strict_template),
                "overwrite": bool(args.overwrite),
            },
            "counts": {
                "rows_read": len(rows),
                "jobs_emitted": emitted,
                "jobs_skipped": skipped,
                "errors": errors,
            },
            "hashes": {
                "input_sha1": _sha1_file(input_path),
                "template_sha1": _sha1_file(template_path),
                "manifest_sha1": None,
            },
            "items": items,
        }

        pre_hash = _sha1_text(_stable_json(payload))
        payload["hashes"]["manifest_sha1"] = pre_hash

        if not args.dry_run:
            _write_text_utf8(manifest_out, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            _write_text_utf8(jobs_file_out, "\n".join(jobs_list) + ("\n" if jobs_list else ""))

        print(
            f"gen_jobs: rows={len(rows)} selected={len(rows_sorted)} emitted={emitted} "
            f"skipped={skipped} errors={errors} out_dir={out_dir}"
        )
        out = {
            "ok": True,
            "exit_code": 0,
            "manifest_path": _norm_path(manifest_out),
            "jobs_file_path": _norm_path(jobs_file_out),
            "counts": payload["counts"],
            "manifest_sha1": payload["hashes"]["manifest_sha1"],
        }
        print(json.dumps(out, ensure_ascii=False))
        return 0
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
