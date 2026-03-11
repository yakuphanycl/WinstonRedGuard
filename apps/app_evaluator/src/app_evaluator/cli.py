from __future__ import annotations

import argparse
import json

from .core import run_evaluation


def _print_result(report: dict, app_path: str) -> None:
    checks = report["checks"]
    print(f"Evaluating: {app_path}")
    print()
    print(f"app_exists .......... {'OK' if checks['app_exists'] else 'FAIL'}")
    print(f"pyproject_exists .... {'OK' if checks['pyproject_exists'] else 'FAIL'}")
    print(f"cli_exists .......... {'OK' if checks['cli_exists'] else 'FAIL'}")
    print(f"tests_exist ......... {'OK' if checks['tests_exist'] else 'FAIL'}")
    print(f"smoke_test_exists ... {'OK' if checks['smoke_test_exists'] else 'FAIL'}")
    print(f"pytest_passed ....... {'OK' if checks['pytest_passed'] else 'FAIL'}")
    print()
    print(f"Score: {report['score']}/6")
    print(f"Result: {'PASS' if report['ok'] else 'FAIL'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app_evaluator")
    subparsers = parser.add_subparsers(dest="command")

    eval_parser = subparsers.add_parser("eval", help="evaluate an app path")
    eval_parser.add_argument("--app-path", required=True)
    eval_parser.add_argument("--json-out")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "eval":
        parser.print_help()
        return 2

    report = run_evaluation(app_path=args.app_path, json_out=args.json_out)
    _print_result(report, args.app_path)

    if args.json_out:
        print(f"JSON report written: {args.json_out}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
