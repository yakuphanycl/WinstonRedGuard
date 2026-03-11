from __future__ import annotations

import argparse
from pathlib import Path

from .core import build_system_status, write_json_status


def _resolve_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "apps").is_dir():
            return candidate
    return cwd


def _print_human(status_report: dict[str, object]) -> None:
    totals = status_report["totals"]
    print("WinstonRedGuard System")
    print(f"apps: {totals['apps']}")
    print(f"ok: {totals['ok']}")
    print(f"partial: {totals['partial']}")
    print(f"broken: {totals['broken']}")
    for app in status_report["apps"]:
        print(f"- {app['name']}: {app['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="wrg_control")
    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser("status", help="show system app status")
    status_parser.add_argument("--json-out", dest="json_out", help="optional output json file path")

    args = parser.parse_args()
    if args.command != "status":
        parser.print_help()
        return 1

    repo_root = _resolve_repo_root()
    try:
        status_report = build_system_status(repo_root)
    except FileNotFoundError:
        print("Error: 'apps' directory was not found.")
        return 1

    _print_human(status_report)

    if args.json_out:
        write_json_status(status_report, Path(args.json_out))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

