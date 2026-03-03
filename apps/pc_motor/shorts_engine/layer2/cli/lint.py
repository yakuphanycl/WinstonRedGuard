from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..core.lint_job import lint_job
from ..core.presets import load_preset, PresetError
from ..core.version import __version__


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.lint")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--job", dest="job")
    p.add_argument("--jobs-file", dest="jobs_file")
    p.add_argument("--jobs-dir", dest="jobs_dir")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    p.add_argument("--fail-on", dest="fail_on", choices=["error", "warn"], default="error")
    p.add_argument("--json-out", dest="json_out")
    p.add_argument("--repo-root", dest="repo_root")
    return p.parse_args(argv)


def _discover_jobs(args: argparse.Namespace) -> tuple[list[Path], str | None]:
    paths: list[Path] = []
    if args.job:
        paths.append(Path(args.job))
    if args.jobs_file:
        jf = Path(args.jobs_file)
        if not jf.exists():
            return [], f"jobs-file not found: {jf}"
        for ln in jf.read_text(encoding="utf-8-sig").splitlines():
            s = ln.strip()
            if s:
                paths.append(Path(s))
    if args.jobs_dir:
        jd = Path(args.jobs_dir)
        if not jd.exists() or not jd.is_dir():
            return [], f"jobs-dir not found or not directory: {jd}"
        paths.extend(sorted([p for p in jd.rglob("*.json") if p.is_file()]))
    if not paths:
        return [], "missing input: provide --job or --jobs-file or --jobs-dir"
    uniq: dict[str, Path] = {}
    for p in paths:
        uniq[str(p.resolve())] = p
    return [uniq[k] for k in sorted(uniq.keys())], None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _lint_one(path: Path) -> dict[str, Any]:
    try:
        job = _load_json(path)
    except Exception as e:
        return {
            "job_path": str(path),
            "ok": False,
            "errors": [{"severity": "error", "code": "JOB_JSON_INVALID", "message": str(e), "path": "$"}],
            "warnings": [],
            "info": [],
            "summary": {"error_count": 1, "warn_count": 0, "info_count": 0},
        }
    preset_obj = None
    pv = job.get("preset") if isinstance(job, dict) else None
    if isinstance(pv, str) and pv.strip():
        try:
            preset_obj = load_preset(pv.strip())
        except PresetError:
            # let lint job flag via missing preset semantics in validate path; for standalone lint keep hard finding
            return {
                "job_path": str(path),
                "ok": False,
                "errors": [
                    {
                        "severity": "error",
                        "code": "PRESET_UNKNOWN",
                        "message": f"unknown preset: {pv.strip()}",
                        "path": "$.preset",
                    }
                ],
                "warnings": [],
                "info": [],
                "summary": {"error_count": 1, "warn_count": 0, "info_count": 0},
            }
    res = lint_job(job if isinstance(job, dict) else {}, preset_obj)
    res["job_path"] = str(path)
    return res


def _print_job_text(res: dict[str, Any]) -> None:
    s = res.get("summary") if isinstance(res.get("summary"), dict) else {}
    ec = int(s.get("error_count") or 0)
    wc = int(s.get("warn_count") or 0)
    print(f"lint: job={res.get('job_path')} ok={res.get('ok')} errors={ec} warnings={wc}")
    top = []
    top.extend((res.get("errors") or [])[:3])
    top.extend((res.get("warnings") or [])[:2])
    for f in top:
        if isinstance(f, dict):
            print(f"  - {f.get('severity')} {f.get('code')} {f.get('path')}: {f.get('message')}")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        jobs, err = _discover_jobs(args)
        if err:
            print(f"ERROR: {err}")
            return 2

        results: list[dict[str, Any]] = []
        total_errors = 0
        total_warns = 0
        error_jobs = 0
        warn_jobs = 0

        for p in jobs:
            res = _lint_one(p)
            results.append(res)
            s = res.get("summary") if isinstance(res.get("summary"), dict) else {}
            ec = int(s.get("error_count") or 0)
            wc = int(s.get("warn_count") or 0)
            total_errors += ec
            total_warns += wc
            if ec > 0:
                error_jobs += 1
            if wc > 0:
                warn_jobs += 1
            if args.fmt == "text":
                _print_job_text(res)

        ok = (error_jobs == 0) if args.fail_on == "error" else (error_jobs == 0 and warn_jobs == 0)
        exit_code = 0 if ok else 2

        report: dict[str, Any] = {
            "ok": bool(ok),
            "exit_code": int(exit_code),
            "jobs": len(results),
            "error_jobs": int(error_jobs),
            "warn_jobs": int(warn_jobs),
            "summary": {"errors": int(total_errors), "warnings": int(total_warns)},
            "items": results,
            "report_path": None,
        }
        if args.json_out:
            rp = Path(args.json_out)
            if rp.parent and str(rp.parent) not in ("", "."):
                rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            report["report_path"] = str(rp)
        print(json.dumps(report, ensure_ascii=False))
        return exit_code
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

