from __future__ import annotations

import argparse
from pathlib import Path

from .core import build_report, write_json_report


def _resolve_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "apps").is_dir():
            return candidate
    return cwd


def _print_report(report: dict[str, object]) -> None:
    print("repo doctor:")
    for app in report["apps"]:
        print(f"- {app['name']}: {app['status']}")
        if app["notes"]:
            print("  notes: " + ", ".join(app["notes"]))


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo_doctor")
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="scan apps directory")
    scan_parser.add_argument("--json-out", dest="json_out", help="optional output json file path")

    args = parser.parse_args()
    if args.command != "scan":
        parser.print_help()
        return 1

    repo_root = _resolve_repo_root()
    try:
        report = build_report(repo_root)
    except FileNotFoundError:
        print("Error: 'apps' directory was not found.")
        return 1

    _print_report(report)

    if args.json_out:
        write_json_report(report, Path(args.json_out))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

