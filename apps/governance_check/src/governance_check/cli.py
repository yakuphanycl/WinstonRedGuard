from __future__ import annotations

import argparse

from .core import format_human_report, run_check, write_json_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="governance_check")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check", help="run governance checks")
    check_parser.add_argument("--json-out", dest="json_out")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "check":
        parser.print_help()
        return 1

    report = run_check()
    print(format_human_report(report))

    if args.json_out:
        write_json_report(report, args.json_out)

    return 1 if int(report["error"]) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
