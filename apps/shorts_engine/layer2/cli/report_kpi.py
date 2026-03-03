from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..core.version import __version__


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_ymd(v: str) -> datetime.date:
    return datetime.strptime(v, "%Y-%m-%d").date()


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _safe_read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        s = raw.strip()
        if not s:
            continue
        try:
            o = json.loads(s)
            if isinstance(o, dict):
                out.append(o)
        except Exception:
            continue
    return out


def _calc_range(start: str | None, end: str | None, days: int) -> tuple[str, str, int]:
    if start and end:
        ds = _parse_ymd(start)
        de = _parse_ymd(end)
        if de < ds:
            raise ValueError("--end must be >= --start")
        dcount = (de - ds).days + 1
        return ds.isoformat(), de.isoformat(), dcount
    if days < 1:
        raise ValueError("--days must be >= 1")
    de = datetime.now(timezone.utc).date()
    ds = de - timedelta(days=days - 1)
    return ds.isoformat(), de.isoformat(), int(days)


def _in_range(day: str, start: str, end: str) -> bool:
    return start <= day <= end


def _pct(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round((float(num) / float(den)) * 100.0, 2)


def _pick_batch_report(plan_dir: Path, plan_obj: dict[str, Any], notes: list[str]) -> Path | None:
    arts = plan_obj.get("artifacts") if isinstance(plan_obj.get("artifacts"), dict) else {}
    p = arts.get("batch_report")
    if isinstance(p, str) and p.strip():
        bp = Path(p.strip())
        if not bp.is_absolute():
            bp = (plan_dir / bp).resolve()
        return bp
    default = plan_dir / "batch_report.json"
    if default.exists():
        return default
    notes.append(f"missing batch_report for plan dir: {plan_dir}")
    return None


def _platform_match(record_platform: str | None, want: str) -> bool:
    if want == "any":
        return True
    rp = str(record_platform or "").strip().lower()
    return rp == want


def _record_published(rec: dict[str, Any]) -> bool:
    status = rec.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip().lower() == "published"
    # backward compatible default for existing journal entries without explicit status
    return True


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.report_kpi")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--data-dir", dest="data_dir", default="shorts_engine/layer2/data")
    p.add_argument("--start", dest="start")
    p.add_argument("--end", dest="end")
    p.add_argument("--days", dest="days", type=int, default=7)
    p.add_argument("--platform", dest="platform", default="any")
    p.add_argument("--json-out", dest="json_out")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
        try:
            start, end, days = _calc_range(args.start, args.end, int(args.days))
        except ValueError as e:
            print(f"ERROR: {e}")
            return 2

        data_dir = Path(args.data_dir)
        plans_root = data_dir / "plans"
        pub_path = data_dir / "publish_journal.jsonl"
        notes: list[str] = []

        plans_days = 0
        planned_ideas_total = 0
        render_target_total = 0
        publish_target_total = 0
        stage_counts = {"planned": 0, "generated": 0, "rendered": 0, "partial": 0, "failed": 0}

        jobs_ok = 0
        jobs_fail = 0
        cached = 0
        rendered = 0

        if plans_root.exists() and plans_root.is_dir():
            day_dirs = [d for d in plans_root.iterdir() if d.is_dir() and len(d.name) == 10]
            for d in sorted(day_dirs, key=lambda x: x.name):
                day = d.name
                if not _in_range(day, start, end):
                    continue
                pp = d / "plan.json"
                if not pp.exists():
                    notes.append(f"missing plan.json: {pp}")
                    continue
                plan = _safe_load_json(pp)
                if not isinstance(plan, dict):
                    notes.append(f"invalid plan.json: {pp}")
                    continue

                plans_days += 1
                sel = plan.get("selection") if isinstance(plan.get("selection"), dict) else {}
                sel_counts = sel.get("counts") if isinstance(sel.get("counts"), dict) else {}
                selected = sel_counts.get("selected")
                if not isinstance(selected, int):
                    keys = sel.get("idea_keys") if isinstance(sel.get("idea_keys"), list) else []
                    selected = len(keys)
                planned_ideas_total += int(selected or 0)

                pol = plan.get("policy") if isinstance(plan.get("policy"), dict) else {}
                render_target_total += int(pol.get("render_target") or 0)
                publish_target_total += int(pol.get("publish_target") or 0)

                st = plan.get("status") if isinstance(plan.get("status"), dict) else {}
                stage = str(st.get("stage") or "planned").strip().lower()
                if stage in stage_counts:
                    stage_counts[stage] += 1
                else:
                    notes.append(f"unknown stage '{stage}' in {pp}")

                bp = _pick_batch_report(d, plan, notes)
                if bp is None:
                    continue
                if not bp.exists():
                    notes.append(f"batch_report not found: {bp}")
                    continue
                br = _safe_load_json(bp)
                if not isinstance(br, dict):
                    notes.append(f"invalid batch_report: {bp}")
                    continue
                jobs_ok += int(br.get("ok_count") or 0)
                jobs_fail += int(br.get("fail_count") or 0)
                # can exist at top-level or summary
                c = br.get("cached_count")
                r = br.get("rendered_count")
                if c is None and isinstance(br.get("summary"), dict):
                    c = br["summary"].get("cached_count")
                if r is None and isinstance(br.get("summary"), dict):
                    r = br["summary"].get("rendered_count")
                cached += int(c or 0)
                rendered += int(r or 0)
        else:
            notes.append(f"plans dir not found: {plans_root}")

        published_count = 0
        platform_counts: dict[str, int] = {}
        idea_keys: set[str] = set()
        for rec in _safe_read_jsonl(pub_path):
            created = str(rec.get("created_at") or "")
            if len(created) < 10:
                continue
            day = created[:10]
            if not _in_range(day, start, end):
                continue
            if not _record_published(rec):
                continue
            if not _platform_match(rec.get("platform"), str(args.platform or "any").strip().lower()):
                continue
            published_count += 1
            plat = str(rec.get("platform") or "unknown").strip() or "unknown"
            platform_counts[plat] = platform_counts.get(plat, 0) + 1
            ik = rec.get("idea_key")
            if isinstance(ik, str) and ik.strip():
                idea_keys.add(ik.strip())

        total_jobs = jobs_ok + jobs_fail
        report = {
            "schema_version": "0.1",
            "created_at": _iso_now(),
            "range": {"start": start, "end": end, "days": int(days)},
            "plans": {
                "days_with_plans": int(plans_days),
                "planned_ideas_total": int(planned_ideas_total),
                "render_target_total": int(render_target_total),
                "publish_target_total": int(publish_target_total),
                "stages": stage_counts,
            },
            "rendering": {
                "jobs_ok": int(jobs_ok),
                "jobs_fail": int(jobs_fail),
                "cached": int(cached),
                "rendered": int(rendered),
                "cache_rate": _pct(cached, total_jobs),
                "fail_rate": _pct(jobs_fail, total_jobs),
            },
            "publishing": {
                "published_count": int(published_count),
                "platform_counts": platform_counts,
                "unique_idea_keys": int(len(idea_keys)),
            },
            "notes": notes,
        }

        out_path = Path(args.json_out) if isinstance(args.json_out, str) and args.json_out.strip() else (data_dir / "reports" / f"kpi_{start}_{end}.json")
        if out_path.parent and str(out_path.parent) not in ("", "."):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

        if args.fmt == "text":
            print(f"kpi range: {start} .. {end} ({days} days)")
            print(f"plans: days={plans_days} planned_ideas={planned_ideas_total} render_target={render_target_total} publish_target={publish_target_total}")
            print(f"rendering: ok={jobs_ok} fail={jobs_fail} cached={cached} rendered={rendered} cache_rate={report['rendering']['cache_rate']}% fail_rate={report['rendering']['fail_rate']}%")
            print(f"publishing: published={published_count} unique_idea_keys={len(idea_keys)}")
            if notes:
                print(f"notes: {len(notes)}")

        print(json.dumps({"ok": True, "exit_code": 0, "range": report["range"], "report_path": str(out_path), "rendering": report["rendering"], "publishing": report["publishing"]}, ensure_ascii=False))
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
