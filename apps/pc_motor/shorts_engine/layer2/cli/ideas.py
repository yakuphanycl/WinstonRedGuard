from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from ..core.idea_store import append_jsonl, idea_key_for, iso_now, load_json, read_jsonl, write_json
from ..core.version import __version__


def _paths(data_dir: Path) -> tuple[Path, Path]:
    return data_dir / "ideas.jsonl", data_dir / "state.json"


def _split_tags(v: str | None) -> list[str]:
    if not isinstance(v, str) or not v.strip():
        return []
    return [x.strip() for x in v.split(",") if x.strip()]


def _state_init() -> dict[str, Any]:
    return {"schema_version": "0.1", "updated_at": iso_now(), "items": {}}


def _load_state(path: Path) -> dict[str, Any]:
    st = load_json(path, _state_init())
    if not isinstance(st, dict):
        st = _state_init()
    if "items" not in st or not isinstance(st["items"], dict):
        st["items"] = {}
    if "schema_version" not in st:
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.ideas")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--data-dir", dest="data_dir", default="shorts_engine/layer2/data", help="ideas/state data dir")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="append a single idea")
    a.add_argument("--topic", dest="topic", default="")
    a.add_argument("--hook", dest="hook", required=True)
    a.add_argument("--body", dest="body", required=True)
    a.add_argument("--ending", dest="ending", required=True)
    a.add_argument("--tags", dest="tags", default="")
    a.add_argument("--lang", dest="lang", default="")
    a.add_argument("--duration-sec", dest="duration_sec", type=int)
    a.add_argument("--source", dest="source", default="manual")
    a.add_argument("--id", dest="source_id")

    ic = sub.add_parser("import-csv", help="import ideas from csv")
    ic.add_argument("--input", dest="input_path", required=True)
    ic.add_argument("--dedup", dest="dedup", action="store_true", default=True)
    ic.add_argument("--no-dedup", dest="dedup", action="store_false")

    ls = sub.add_parser("list", help="list ideas with filters")
    ls.add_argument("--status", dest="status", default="any")
    ls.add_argument("--tag", dest="tag")
    ls.add_argument("--limit", dest="limit", type=int, default=20)

    bc = sub.add_parser("build-csv", help="build deterministic csv for gen_jobs")
    bc.add_argument("--out", dest="out_path")
    bc.add_argument("--status", dest="status", default="queued")
    bc.add_argument("--tag", dest="tag")
    bc.add_argument("--limit", dest="limit", type=int)
    bc.add_argument("--shuffle", dest="shuffle", action="store_true", default=False)
    bc.add_argument("--only-keys", dest="only_keys_path", help="path to newline-separated idea_keys")
    bc.add_argument("--keys", dest="keys_csv", help="comma-separated idea_keys")

    mk = sub.add_parser("mark", help="update idea state")
    mk.add_argument("--idea-key", dest="idea_key", required=True)
    mk.add_argument("--status", dest="status", required=True, choices=["queued", "rendered", "published", "dropped"])
    mk.add_argument("--note", dest="note")
    mk.add_argument("--run-id", dest="run_id")
    mk.add_argument("--job-path", dest="job_path")
    mk.add_argument("--batch-run-id", dest="batch_run_id")

    return p.parse_args(argv)


def _cmd_add(args: argparse.Namespace, data_dir: Path) -> int:
    ideas_path, state_path = _paths(data_dir)
    item = {
        "id": args.source_id if args.source_id else None,
        "created_at": iso_now(),
        "topic": str(args.topic or ""),
        "hook": str(args.hook or ""),
        "body": str(args.body or ""),
        "ending": str(args.ending or ""),
        "lang": str(args.lang or "") or None,
        "duration_sec": int(args.duration_sec) if args.duration_sec is not None else None,
        "tags": _split_tags(args.tags),
        "source": str(args.source or "manual"),
    }
    k = idea_key_for(item["hook"], item["body"], item["ending"])
    item["idea_key"] = k
    append_jsonl(ideas_path, item)

    st = _load_state(state_path)
    _ensure_state_item(st, k)
    st["updated_at"] = iso_now()
    write_json(state_path, st)

    print(f"ideas add: appended idea_key={k}")
    print(json.dumps({"ok": True, "exit_code": 0, "idea_key": k, "path": str(ideas_path), "appended": True}, ensure_ascii=False))
    return 0


def _cmd_import_csv(args: argparse.Namespace, data_dir: Path) -> int:
    ip = Path(args.input_path)
    if not ip.exists():
        print(f"ERROR: input csv not found: {ip}")
        return 2
    ideas_path, state_path = _paths(data_dir)
    existing = _load_ideas_with_key(ideas_path)
    seen = set(str(x.get("idea_key")) for x in existing)
    imported = 0
    skipped = 0
    rows_read = 0
    with ip.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_read += 1
            hook = str((row or {}).get("hook") or "")
            body = str((row or {}).get("body") or "")
            ending = str((row or {}).get("ending") or "")
            if not hook or not body or not ending:
                skipped += 1
                continue
            k = idea_key_for(hook, body, ending)
            if bool(args.dedup) and k in seen:
                skipped += 1
                continue
            seen.add(k)
            item = {
                "id": str((row or {}).get("id") or "") or None,
                "created_at": iso_now(),
                "topic": str((row or {}).get("topic") or ""),
                "hook": hook,
                "body": body,
                "ending": ending,
                "lang": str((row or {}).get("lang") or "") or None,
                "duration_sec": int(float((row or {}).get("duration_sec"))) if str((row or {}).get("duration_sec") or "").strip() else None,
                "tags": _split_tags(str((row or {}).get("tags") or "")),
                "source": "import",
                "idea_key": k,
            }
            append_jsonl(ideas_path, item)
            imported += 1

    st = _load_state(state_path)
    for k in seen:
        _ensure_state_item(st, k)
    st["updated_at"] = iso_now()
    write_json(state_path, st)

    out = {"ok": True, "exit_code": 0, "rows_read": rows_read, "imported": imported, "skipped": skipped}
    print(f"ideas import-csv: rows={rows_read} imported={imported} skipped={skipped}")
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _cmd_list(args: argparse.Namespace, data_dir: Path) -> int:
    ideas_path, state_path = _paths(data_dir)
    ideas = _load_ideas_with_key(ideas_path)
    st = _load_state(state_path)
    tag_filter = str(args.tag or "").strip().lower()
    status_filter = str(args.status or "any").strip().lower()
    out_items: list[dict[str, Any]] = []
    for it in ideas:
        k = str(it.get("idea_key"))
        si = (st.get("items") or {}).get(k, {})
        status = str((si or {}).get("status") or "queued")
        if status_filter != "any" and status != status_filter:
            continue
        tags = it.get("tags")
        tags_list = tags if isinstance(tags, list) else []
        if tag_filter:
            tags_norm = [str(x).strip().lower() for x in tags_list]
            if tag_filter not in tags_norm:
                continue
        out_items.append(
            {
                "idea_key": k,
                "status": status,
                "topic": it.get("topic"),
                "hook": it.get("hook"),
                "lang": it.get("lang"),
                "tags": tags_list,
            }
        )
    lim = int(args.limit) if args.limit is not None else 20
    if lim > 0:
        out_items = out_items[-lim:]
    print(f"ideas list: count={len(out_items)}")
    print(json.dumps({"ok": True, "exit_code": 0, "count": len(out_items), "items": out_items}, ensure_ascii=False))
    return 0


def _cmd_build_csv(args: argparse.Namespace, data_dir: Path) -> int:
    ideas_path, state_path = _paths(data_dir)
    out_path = Path(args.out_path) if args.out_path else (data_dir / "inputs.csv")
    ideas = _load_ideas_with_key(ideas_path)
    st = _load_state(state_path)
    status_filter = str(args.status or "queued").strip().lower()
    tag_filter = str(args.tag or "").strip().lower()
    key_allow: set[str] | None = None
    if isinstance(args.keys_csv, str) and args.keys_csv.strip():
        key_allow = set(x.strip() for x in args.keys_csv.split(",") if x.strip())
    if isinstance(args.only_keys_path, str) and args.only_keys_path.strip():
        kp = Path(args.only_keys_path)
        if not kp.exists():
            print(f"ERROR: only-keys file not found: {kp}")
            return 2
        lines = [x.strip() for x in kp.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
        if key_allow is None:
            key_allow = set(lines)
        else:
            key_allow.update(lines)

    selected: list[dict[str, Any]] = []
    for it in ideas:
        k = str(it.get("idea_key"))
        if key_allow is not None and k not in key_allow:
            continue
        si = (st.get("items") or {}).get(k, {})
        status = str((si or {}).get("status") or "queued")
        if status_filter != "any" and status != status_filter:
            continue
        tags = it.get("tags")
        tags_list = tags if isinstance(tags, list) else []
        if tag_filter:
            tags_norm = [str(x).strip().lower() for x in tags_list]
            if tag_filter not in tags_norm:
                continue
        rr = dict(it)
        rr["idea_key"] = k
        selected.append(rr)
    selected.sort(key=lambda x: str(x.get("idea_key") or ""))
    if args.limit is not None and int(args.limit) > 0:
        selected = selected[: int(args.limit)]

    headers = ["id", "hook", "body", "ending", "duration_sec", "lang", "tags"]
    if out_path.parent and str(out_path.parent) not in ("", "."):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for it in selected:
            w.writerow(
                {
                    "id": it.get("id") or it.get("idea_key"),
                    "hook": it.get("hook") or "",
                    "body": it.get("body") or "",
                    "ending": it.get("ending") or "",
                    "duration_sec": it.get("duration_sec"),
                    "lang": it.get("lang") or "",
                    "tags": ",".join(it.get("tags") or []),
                }
            )
    print(f"ideas build-csv: selected={len(selected)} out={out_path}")
    print(json.dumps({"ok": True, "exit_code": 0, "out": str(out_path), "count": len(selected)}, ensure_ascii=False))
    return 0


def _cmd_mark(args: argparse.Namespace, data_dir: Path) -> int:
    _, state_path = _paths(data_dir)
    st = _load_state(state_path)
    k = str(args.idea_key or "").strip()
    if not k:
        print("ERROR: missing --idea-key")
        return 2
    si = _ensure_state_item(st, k)
    si["status"] = str(args.status)
    si["last_changed_at"] = iso_now()
    if args.note is not None:
        si["note"] = str(args.note)
    if args.run_id is not None:
        si["run_id"] = str(args.run_id)
    if args.job_path is not None:
        si["job_path"] = str(args.job_path)
    if args.batch_run_id is not None:
        si["batch_run_id"] = str(args.batch_run_id)
    st["updated_at"] = iso_now()
    write_json(state_path, st)
    print(f"ideas mark: idea_key={k} status={si['status']}")
    print(json.dumps({"ok": True, "exit_code": 0, "idea_key": k, "status": si["status"]}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        if not args.cmd:
            print("ERROR: missing subcommand")
            return 2
        data_dir = Path(args.data_dir)
        if args.cmd == "add":
            return _cmd_add(args, data_dir)
        if args.cmd == "import-csv":
            return _cmd_import_csv(args, data_dir)
        if args.cmd == "list":
            return _cmd_list(args, data_dir)
        if args.cmd == "build-csv":
            return _cmd_build_csv(args, data_dir)
        if args.cmd == "mark":
            return _cmd_mark(args, data_dir)
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
