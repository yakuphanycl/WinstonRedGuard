from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.idea_store import append_jsonl, idea_key_for, iso_now, load_json, read_jsonl, write_json
from ..core.version import __version__


def _data_paths(data_dir: Path) -> tuple[Path, Path, Path]:
    ideas = data_dir / "ideas.jsonl"
    state = data_dir / "state.json"
    plans = data_dir / "plans"
    return ideas, state, plans


def _state_init() -> dict[str, Any]:
    return {"schema_version": "0.1", "updated_at": iso_now(), "items": {}}


def _load_state(path: Path) -> dict[str, Any]:
    st = load_json(path, _state_init())
    if not isinstance(st, dict):
        st = _state_init()
    if not isinstance(st.get("items"), dict):
        st["items"] = {}
    if not st.get("schema_version"):
        st["schema_version"] = "0.1"
    return st


def _ensure_state_item(state: dict[str, Any], key: str) -> dict[str, Any]:
    items = state.setdefault("items", {})
    if key not in items or not isinstance(items[key], dict):
        items[key] = {
            "status": "queued",
            "last_changed_at": iso_now(),
            "note": None,
            "run_id": None,
            "job_path": None,
            "batch_run_id": None,
        }
    return items[key]


def _load_ideas_with_key(ideas_path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(ideas_path)
    out: list[dict[str, Any]] = []
    for r in rows:
        hook = str(r.get("hook") or "")
        body = str(r.get("body") or "")
        ending = str(r.get("ending") or "")
        k = str(r.get("idea_key") or idea_key_for(hook, body, ending))
        rr = dict(r)
        rr["idea_key"] = k
        out.append(rr)
    return out


def _date_ymd(v: str | None) -> str:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _plan_paths(plans_dir: Path, day: str) -> tuple[Path, Path, Path]:
    root = plans_dir / day
    return root, root / "plan.json", root / "done.jsonl"


def _append_done(done_path: Path, action: str, ok: bool, detail: dict[str, Any] | None = None) -> None:
    ev = {
        "created_at": iso_now(),
        "action": action,
        "ok": bool(ok),
        "detail": detail or {},
    }
    append_jsonl(done_path, ev)


def _parse_last_json_line(lines: str) -> dict[str, Any] | None:
    for raw in reversed((lines or "").splitlines()):
        s = raw.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _run_cli(module_name: str, args: list[str]) -> tuple[int, str, dict[str, Any] | None]:
    cmd = [sys.executable, "-m", module_name] + args
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = p.stdout or ""
    return int(p.returncode), out, _parse_last_json_line(out)


def _module_name(short_name: str) -> str:
    pkg = (__package__ or "").strip()
    if pkg.startswith("shorts_engine."):
        return f"shorts_engine.layer2.cli.{short_name}"
    return f"layer2.cli.{short_name}"


def _default_template_path(plan_dir: Path) -> Path:
    p = plan_dir / "template.json"
    if p.exists():
        return p
    obj = {
        "version": "0.5",
        "output": {"path": "output/{{id}}.mp4"},
        "video": {"resolution": "1080x1920", "fps": 30, "duration_sec": 8},
        "hook": "{{hook}}",
        "pattern_break": "{{body}}",
        "loop_ending": "{{ending}}",
        "subtitles": {
            "items": [
                {"text": "{{hook}}"},
                {"text": "{{body}}"},
                {"text": "{{ending}}"},
            ]
        },
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _select_queued_ideas(
    ideas: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    tag: str | None,
    mode: str,
    seed: int,
    limit: int,
    day: str,
) -> tuple[list[dict[str, Any]], int]:
    items = state.get("items") if isinstance(state.get("items"), dict) else {}
    tag_norm = str(tag or "").strip().lower()
    queued: list[dict[str, Any]] = []
    for idx, it in enumerate(ideas):
        k = str(it.get("idea_key") or "")
        if not k:
            continue
        si = items.get(k, {}) if isinstance(items, dict) else {}
        status = str((si or {}).get("status") or "queued")
        if status != "queued":
            continue
        if tag_norm:
            tags = it.get("tags")
            tags_list = tags if isinstance(tags, list) else []
            if tag_norm not in [str(x).strip().lower() for x in tags_list]:
                continue
        rr = dict(it)
        rr["_idx"] = idx
        queued.append(rr)

    if mode == "oldest":
        queued.sort(key=lambda x: (str(x.get("created_at") or ""), int(x.get("_idx", 0)), str(x.get("idea_key") or "")))
    elif mode == "round_robin":
        queued.sort(key=lambda x: str(x.get("idea_key") or ""))
        if queued:
            day_n = int(day.replace("-", "")) if day.replace("-", "").isdigit() else 0
            shift = day_n % len(queued)
            queued = queued[shift:] + queued[:shift]
    else:  # random_seeded
        queued.sort(key=lambda x: str(x.get("idea_key") or ""))
        rnd = random.Random(seed)
        rnd.shuffle(queued)

    return queued[: max(0, int(limit))], len(queued)


def _plan_skeleton(day: str, *, ideas_target: int, render_target: int, publish_target: int, selection_mode: str, tag: str | None, max_fail: int, continue_on_error: bool) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "date": day,
        "created_at": iso_now(),
        "policy": {
            "ideas_target": int(ideas_target),
            "render_target": int(render_target),
            "publish_target": int(publish_target),
            "selection_mode": selection_mode,
            "tag": tag if tag else None,
            "max_fail": int(max_fail),
            "continue_on_error": bool(continue_on_error),
        },
        "selection": {
            "idea_keys": [],
            "counts": {"queued_available": 0, "selected": 0},
        },
        "artifacts": {
            "inputs_csv": None,
            "gen_out_dir": None,
            "manifest_path": None,
            "jobs_file": None,
            "jobset_path": None,
            "batch_report": None,
        },
        "status": {"stage": "planned", "note": None},
    }


def _cmd_make(args: argparse.Namespace, data_dir: Path) -> int:
    ideas_path, state_path, plans_dir = _data_paths(data_dir)
    day = _date_ymd(args.date)
    plan_dir, plan_path, done_path = _plan_paths(plans_dir, day)
    ideas = _load_ideas_with_key(ideas_path)
    state = _load_state(state_path)

    seed = int(args.seed) if args.seed is not None else int(day.replace("-", "") or "0")
    selected, queued_available = _select_queued_ideas(
        ideas,
        state,
        tag=args.tag,
        mode=args.selection,
        seed=seed,
        limit=int(args.ideas_target),
        day=day,
    )

    plan = _plan_skeleton(
        day,
        ideas_target=int(args.ideas_target),
        render_target=int(args.render_target),
        publish_target=int(args.publish_target),
        selection_mode=str(args.selection),
        tag=args.tag,
        max_fail=int(args.max_fail),
        continue_on_error=bool(args.continue_on_error),
    )
    keys = [str(x.get("idea_key")) for x in selected if str(x.get("idea_key") or "").strip()]
    plan["selection"]["idea_keys"] = keys
    plan["selection"]["counts"] = {"queued_available": int(queued_available), "selected": len(keys)}

    plan_dir.mkdir(parents=True, exist_ok=True)
    write_json(plan_path, plan)
    _append_done(done_path, "plan_make", True, {"selected": len(keys), "queued_available": queued_available})

    print(f"plan make: date={day} selected={len(keys)} path={plan_path}")
    print(json.dumps({"ok": True, "exit_code": 0, "plan_path": str(plan_path), "selected": len(keys)}, ensure_ascii=False))
    return 0


def _cmd_build(args: argparse.Namespace, data_dir: Path) -> int:
    _, _, plans_dir = _data_paths(data_dir)
    day = _date_ymd(args.date)
    plan_dir, plan_path, done_path = _plan_paths(plans_dir, day)
    if not plan_path.exists():
        print(f"ERROR: plan not found for date={day}: {plan_path}")
        return 2
    plan = load_json(plan_path, {})
    if not isinstance(plan, dict):
        print(f"ERROR: invalid plan json: {plan_path}")
        return 2

    arts = plan.get("artifacts") if isinstance(plan.get("artifacts"), dict) else {}
    inputs_csv = Path(str(arts.get("inputs_csv") or (plan_dir / "inputs.csv")))
    gen_out = Path(str(arts.get("gen_out_dir") or (plan_dir / "jobs")))
    manifest_path = Path(str(arts.get("manifest_path") or (gen_out / "manifest.json")))
    jobs_file = Path(str(arts.get("jobs_file") or (gen_out / "jobs.txt")))
    jobset_path = Path(str(arts.get("jobset_path") or (plan_dir / "jobset.json")))

    if (not bool(args.force)) and inputs_csv.exists() and manifest_path.exists() and jobs_file.exists() and jobset_path.exists():
        plan["artifacts"] = {
            "inputs_csv": str(inputs_csv),
            "gen_out_dir": str(gen_out),
            "manifest_path": str(manifest_path),
            "jobs_file": str(jobs_file),
            "jobset_path": str(jobset_path),
            "batch_report": plan.get("artifacts", {}).get("batch_report"),
        }
        plan.setdefault("status", {})["stage"] = "generated"
        write_json(plan_path, plan)
        _append_done(done_path, "plan_build", True, {"reused": True, "inputs_csv": str(inputs_csv)})
        print(f"plan build: reused existing artifacts date={day}")
        print(json.dumps({"ok": True, "exit_code": 0, "plan_path": str(plan_path), "stage": "generated", "reused": True}, ensure_ascii=False))
        return 0

    keys = plan.get("selection", {}).get("idea_keys")
    if not isinstance(keys, list) or not keys:
        print("ERROR: plan.selection.idea_keys empty")
        return 2

    keys_file = plan_dir / "keys.txt"
    keys_file.write_text("\n".join(str(x) for x in keys if str(x).strip()) + "\n", encoding="utf-8", newline="\n")

    ideas_mod = _module_name("ideas")
    rc, out, payload = _run_cli(
        ideas_mod,
        [
            "--data-dir",
            str(data_dir),
            "build-csv",
            "--out",
            str(inputs_csv),
            "--status",
            "queued",
            "--only-keys",
            str(keys_file),
        ],
    )
    if rc != 0 or not isinstance(payload, dict) or not bool(payload.get("ok", False)):
        _append_done(done_path, "plan_build_inputs_csv", False, {"rc": rc, "output": out[-1000:]})
        print(out)
        print("ERROR: ideas build-csv failed")
        return 2

    template_path = Path(args.template) if isinstance(args.template, str) and args.template.strip() else _default_template_path(plan_dir)
    if not template_path.exists():
        print(f"ERROR: template not found: {template_path}")
        return 2

    gen_mod = _module_name("gen_jobs")
    rc, out, payload = _run_cli(
        gen_mod,
        [
            "--input",
            str(inputs_csv),
            "--template",
            str(template_path),
            "--out-dir",
            str(gen_out),
            "--manifest-out",
            str(manifest_path),
            "--jobs-file-out",
            str(jobs_file),
        ],
    )
    if rc != 0 or not isinstance(payload, dict) or not bool(payload.get("ok", False)):
        _append_done(done_path, "plan_build_gen_jobs", False, {"rc": rc, "output": out[-1000:]})
        print(out)
        print("ERROR: gen_jobs failed")
        return 2

    jobset_mod = _module_name("jobset")
    rc, out, payload = _run_cli(
        jobset_mod,
        [
            "build",
            "--jobs-file",
            str(jobs_file),
            "--out",
            str(jobset_path),
        ],
    )
    if rc != 0 or not isinstance(payload, dict) or not bool(payload.get("ok", False)):
        _append_done(done_path, "plan_build_jobset", False, {"rc": rc, "output": out[-1000:]})
        print(out)
        print("ERROR: jobset build failed")
        return 2

    plan["artifacts"] = {
        "inputs_csv": str(inputs_csv),
        "gen_out_dir": str(gen_out),
        "manifest_path": str(manifest_path),
        "jobs_file": str(jobs_file),
        "jobset_path": str(jobset_path),
        "batch_report": plan.get("artifacts", {}).get("batch_report"),
    }
    plan.setdefault("status", {})["stage"] = "generated"
    plan["status"]["note"] = None
    write_json(plan_path, plan)
    _append_done(
        done_path,
        "plan_build",
        True,
        {
            "inputs_csv": str(inputs_csv),
            "manifest_path": str(manifest_path),
            "jobs_file": str(jobs_file),
            "jobset_path": str(jobset_path),
        },
    )

    print(f"plan build: date={day} stage=generated")
    print(
        json.dumps(
            {
                "ok": True,
                "exit_code": 0,
                "plan_path": str(plan_path),
                "stage": "generated",
                "inputs_csv": str(inputs_csv),
                "jobs_file": str(jobs_file),
                "manifest_path": str(manifest_path),
                "jobset_path": str(jobset_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _try_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _extract_idea_key_from_job(job_path: str) -> str | None:
    try:
        obj = json.loads(Path(job_path).read_text(encoding="utf-8-sig"))
        if not isinstance(obj, dict):
            return None
        hook = str(obj.get("hook") or "")
        pb = str(obj.get("pattern_break") or "")
        le = str(obj.get("loop_ending") or "")
        if hook and pb and le:
            return idea_key_for(hook, pb, le)
        subs = obj.get("subtitles")
        if isinstance(subs, dict) and isinstance(subs.get("items"), list):
            texts: list[str] = []
            for it in subs["items"]:
                if isinstance(it, dict):
                    t = it.get("text")
                    if isinstance(t, str) and t.strip():
                        texts.append(t.strip())
            if len(texts) >= 3:
                return idea_key_for(texts[0], texts[1], texts[2])
    except Exception:
        return None
    return None


def _cmd_render(args: argparse.Namespace, data_dir: Path) -> int:
    ideas_path, state_path, plans_dir = _data_paths(data_dir)
    _ = ideas_path  # reserved for future direct mapping support
    day = _date_ymd(args.date)
    plan_dir, plan_path, done_path = _plan_paths(plans_dir, day)
    if not plan_path.exists():
        print(f"ERROR: plan not found for date={day}: {plan_path}")
        return 2
    plan = load_json(plan_path, {})
    if not isinstance(plan, dict):
        print(f"ERROR: invalid plan json: {plan_path}")
        return 2

    arts = plan.get("artifacts") if isinstance(plan.get("artifacts"), dict) else {}
    jobs_file = arts.get("jobs_file")
    jobset_path = arts.get("jobset_path")
    if not isinstance(jobs_file, str) and not isinstance(jobset_path, str):
        print("ERROR: plan artifacts missing jobs_file/jobset_path; run plan build first")
        return 2

    continue_on_error = bool(args.continue_on_error)
    if args.max_fail is None:
        max_fail = int(plan.get("policy", {}).get("max_fail") or 1)
    else:
        max_fail = int(args.max_fail)

    batch_report = plan_dir / "batch_report.json"
    batch_mod = _module_name("render_batch")
    batch_args = ["--json-out", str(batch_report)]
    if isinstance(jobs_file, str) and jobs_file.strip() and Path(jobs_file).exists():
        batch_args.extend(["--jobs-file", jobs_file])
    elif isinstance(jobset_path, str) and jobset_path.strip() and Path(jobset_path).exists():
        batch_args.extend(["--jobset", jobset_path])
    else:
        print("ERROR: jobs_file/jobset_path not found on disk")
        return 2

    if continue_on_error:
        batch_args.append("--continue-on-error")
    else:
        batch_args.append("--stop-on-error")
    if max_fail >= 1:
        batch_args.extend(["--max-fail", str(max_fail)])

    rc, out, payload = _run_cli(batch_mod, batch_args)
    if payload is None:
        _append_done(done_path, "plan_render", False, {"rc": rc, "output": out[-1000:]})
        print(out)
        print("ERROR: render_batch did not return parseable JSON")
        return 2 if rc in (0, 2) else 1

    plan.setdefault("artifacts", {})["batch_report"] = str(batch_report)
    fail_count = int(payload.get("summary", {}).get("fail") or payload.get("fail_count") or 0)
    ok_count = int(payload.get("summary", {}).get("ok") or payload.get("ok_count") or 0)
    stage = "rendered" if rc == 0 and fail_count == 0 else "partial"
    plan.setdefault("status", {})["stage"] = stage
    plan["status"]["note"] = None if stage == "rendered" else "render had failures"

    state = _load_state(state_path)
    report_obj = _try_load_json(batch_report)
    marked = 0
    if isinstance(report_obj, dict) and isinstance(report_obj.get("items"), list):
        for it in report_obj["items"]:
            if not isinstance(it, dict):
                continue
            result_rc = it.get("result_rc")
            if not isinstance(result_rc, int) or result_rc != 0:
                continue
            job_path = it.get("job_path")
            run_id = it.get("run_id")
            batch_run_id = report_obj.get("batch_run_id")
            if not isinstance(job_path, str) or not job_path.strip():
                continue
            idea_key = _extract_idea_key_from_job(job_path)
            if not idea_key:
                continue
            si = _ensure_state_item(state, idea_key)
            si["status"] = "rendered"
            si["last_changed_at"] = iso_now()
            si["run_id"] = str(run_id) if run_id is not None else si.get("run_id")
            si["job_path"] = str(job_path)
            si["batch_run_id"] = str(batch_run_id) if batch_run_id is not None else si.get("batch_run_id")
            marked += 1
    state["updated_at"] = iso_now()
    write_json(state_path, state)

    write_json(plan_path, plan)
    _append_done(
        done_path,
        "plan_render",
        rc in (0, 2),
        {
            "rc": rc,
            "ok_count": ok_count,
            "fail_count": fail_count,
            "batch_report": str(batch_report),
            "marked_rendered": marked,
        },
    )

    print(f"plan render: date={day} stage={stage} ok={ok_count} fail={fail_count}")
    print(
        json.dumps(
            {
                "ok": rc == 0,
                "exit_code": 0 if rc == 0 else 2,
                "plan_path": str(plan_path),
                "batch_report": str(batch_report),
                "stage": stage,
                "ok_count": ok_count,
                "fail_count": fail_count,
                "marked_rendered": marked,
            },
            ensure_ascii=False,
        )
    )
    return 0 if rc == 0 else 2


def _cmd_mark_published(args: argparse.Namespace, data_dir: Path) -> int:
    _, state_path, plans_dir = _data_paths(data_dir)
    day = _date_ymd(args.date)
    _, plan_path, done_path = _plan_paths(plans_dir, day)
    if not plan_path.exists():
        print(f"ERROR: plan not found for date={day}: {plan_path}")
        return 2
    plan = load_json(plan_path, {})
    keys = plan.get("selection", {}).get("idea_keys") if isinstance(plan, dict) else None
    if not isinstance(keys, list) or not keys:
        print("ERROR: plan.selection.idea_keys empty")
        return 2
    st = _load_state(state_path)
    touched = 0
    for k in keys:
        kk = str(k or "").strip()
        if not kk:
            continue
        si = _ensure_state_item(st, kk)
        si["status"] = "published"
        si["last_changed_at"] = iso_now()
        touched += 1
    st["updated_at"] = iso_now()
    write_json(state_path, st)

    if isinstance(plan, dict):
        plan.setdefault("status", {})["stage"] = "published"
        plan["status"]["note"] = None
        write_json(plan_path, plan)

    _append_done(done_path, "plan_mark_published", True, {"count": touched})
    print(f"plan mark-published: date={day} count={touched}")
    print(json.dumps({"ok": True, "exit_code": 0, "count": touched, "plan_path": str(plan_path)}, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.plan")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--data-dir", dest="data_dir", default="shorts_engine/layer2/data", help="ideas/state/plans data dir")
    sub = p.add_subparsers(dest="cmd")

    mk = sub.add_parser("make", help="create daily plan")
    mk.add_argument("--date", dest="date")
    mk.add_argument("--ideas-target", dest="ideas_target", type=int, default=20)
    mk.add_argument("--render-target", dest="render_target", type=int, default=20)
    mk.add_argument("--publish-target", dest="publish_target", type=int, default=0)
    mk.add_argument("--tag", dest="tag")
    mk.add_argument("--selection", dest="selection", choices=["oldest", "round_robin", "random_seeded"], default="oldest")
    mk.add_argument("--seed", dest="seed", type=int)
    mk.add_argument("--max-fail", dest="max_fail", type=int, default=1)
    mk.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=False)

    b = sub.add_parser("build", help="generate artifacts for a plan")
    b.add_argument("--date", dest="date")
    b.add_argument("--template", dest="template", help="optional template json path for gen_jobs")
    b.add_argument("--force", dest="force", action="store_true", default=False)

    r = sub.add_parser("render", help="render plan jobs via render_batch")
    r.add_argument("--date", dest="date")
    r.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True)
    r.add_argument("--max-fail", dest="max_fail", type=int)

    mp = sub.add_parser("mark-published", help="mark selected plan ideas as published")
    mp.add_argument("--date", dest="date")

    return p


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)
        if not args.cmd:
            parser.print_help()
            return 2
        data_dir = Path(args.data_dir)
        if args.cmd == "make":
            return _cmd_make(args, data_dir)
        if args.cmd == "build":
            return _cmd_build(args, data_dir)
        if args.cmd == "render":
            return _cmd_render(args, data_dir)
        if args.cmd == "mark-published":
            return _cmd_mark_published(args, data_dir)
        print(f"ERROR: unknown subcommand: {args.cmd}")
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
