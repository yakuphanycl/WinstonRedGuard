from __future__ import annotations

import argparse
import json

from .bundle_engine import suggest_bundle
from .core import get_required_record, load_records
from .inspector import inspect_app
from .package_manager import mark_packaged
from .refine_planner import build_refine_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="refinery", description="WRG app productization refinery")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="inspect one app from apps/<app_name>")
    inspect_parser.add_argument("app_name")

    show_parser = subparsers.add_parser("show", help="show one refinery record")
    show_parser.add_argument("app_name")

    subparsers.add_parser("list", help="list refinery records")

    refine_parser = subparsers.add_parser("refine-plan", help="build refine plan from inspect signals")
    refine_parser.add_argument("app_name")

    package_parser = subparsers.add_parser("package-mark", help="mark app as packaged")
    package_parser.add_argument("app_name")
    package_parser.add_argument("--market-ready", action="store_true")

    bundle_parser = subparsers.add_parser("bundle-suggest", help="suggest bundle candidates")
    bundle_parser.add_argument("app_name")

    return parser


def _print_list(rows: list[dict]) -> None:
    if not rows:
        print("no records")
        return
    ordered = sorted(rows, key=lambda row: str(row.get("app_name", "")))
    for row in ordered:
        print(
            f"- {row.get('app_name')}: status={row.get('status')} "
            f"product_score={row.get('product_score')}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect":
            row = inspect_app(args.app_name)
            print(
                f"inspect done: {row['app_name']} status={row['status']} "
                f"product_score={row['product_score']}"
            )
            return 0

        if args.command == "show":
            row = get_required_record(args.app_name)
            print(json.dumps(row, indent=2, ensure_ascii=False))
            return 0

        if args.command == "list":
            _print_list(load_records())
            return 0

        if args.command == "refine-plan":
            row = build_refine_plan(args.app_name)
            print(f"refine plan updated: {row['app_name']} status={row['status']}")
            return 0

        if args.command == "package-mark":
            row = mark_packaged(args.app_name, market_ready=bool(args.market_ready))
            print(f"package mark updated: {row['app_name']} status={row['status']}")
            return 0

        if args.command == "bundle-suggest":
            row = suggest_bundle(args.app_name)
            print(
                f"bundle suggestions updated: {row['app_name']} "
                f"candidates={','.join(row.get('bundle_candidates', [])) or '-'}"
            )
            return 0

        parser.print_help()
        return 1
    except ValueError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
