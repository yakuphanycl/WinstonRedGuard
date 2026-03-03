from __future__ import annotations

import argparse
import json

from ..core.presets import load_preset, list_presets, preset_hash, PresetError
from ..core.version import __version__


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.presets")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("list", help="list available presets")
    show = sub.add_parser("show", help="show preset JSON")
    show.add_argument("--name", dest="name", required=True)
    hs = sub.add_parser("hash", help="print preset hash")
    hs.add_argument("--name", dest="name", required=True)
    return p.parse_args(argv)


def _cmd_list() -> int:
    items = list_presets()
    print(f"presets list: count={len(items)}")
    for it in items:
        print(f"- {it['name']}: {it.get('description','')}")
    print(json.dumps({"ok": True, "exit_code": 0, "count": len(items), "items": items}, ensure_ascii=False))
    return 0


def _cmd_show(name: str) -> int:
    try:
        obj = load_preset(name)
    except PresetError as e:
        print(f"ERROR: {e}")
        return 2
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {"ok": True, "exit_code": 0, "name": obj.get("name"), "schema_version": obj.get("schema_version"), "hash": preset_hash(obj)},
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_hash(name: str) -> int:
    try:
        obj = load_preset(name)
    except PresetError as e:
        print(f"ERROR: {e}")
        return 2
    h = preset_hash(obj)
    print(f"preset hash: name={obj.get('name')} hash={h}")
    print(json.dumps({"ok": True, "exit_code": 0, "name": obj.get("name"), "preset_hash": h}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        if args.cmd == "list":
            return _cmd_list()
        if args.cmd == "show":
            return _cmd_show(args.name)
        if args.cmd == "hash":
            return _cmd_hash(args.name)
        print("ERROR: missing subcommand (list|show|hash)")
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

