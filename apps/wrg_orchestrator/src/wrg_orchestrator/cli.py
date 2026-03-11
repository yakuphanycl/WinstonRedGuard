from __future__ import annotations

import argparse
from pathlib import Path

from .core import execute_workflow, get_workflows, resolve_repo_root, write_json_result


def _print_workflow_result(result: dict[str, object]) -> None:
    print(f"workflow: {result['workflow']}")
    print("steps:")
    for step in result["steps"]:
        print(f"- {step['name']}: {step['status']}")
    print("")
    print("summary:")
    print(f"apps: {result['summary']['apps']}")
    print(f"ok: {result['summary']['ok']}")
    print(f"partial: {result['summary']['partial']}")
    print(f"broken: {result['summary']['broken']}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="wrg_orchestrator")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="list available workflows")

    run_parser = subparsers.add_parser("run", help="run a workflow")
    run_parser.add_argument("workflow_name", help="workflow name")
    run_parser.add_argument("--json-out", dest="json_out", help="optional output json file path")

    args = parser.parse_args()

    if args.command == "list":
        for workflow_name in get_workflows():
            print(workflow_name)
        return 0

    if args.command == "run":
        repo_root = resolve_repo_root()
        try:
            result = execute_workflow(args.workflow_name, repo_root)
        except FileNotFoundError:
            print("Error: 'apps' directory was not found.")
            return 1
        except ValueError as exc:
            print(f"Error: {exc}")
            return 1

        _print_workflow_result(result)
        if args.json_out:
            write_json_result(result, Path(args.json_out))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

