from __future__ import annotations

import argparse

from devtool_genome.core.catalog import list_tools
from devtool_genome.core.query import find_tools


def main() -> int:
    parser = argparse.ArgumentParser(prog="dgen")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all tools")

    find_parser = sub.add_parser("find", help="Find tools by keyword")
    find_parser.add_argument("keyword")

    args = parser.parse_args()

    if args.command == "list":
        for tool in list_tools():
            print(f"{tool.id} | {tool.category} | {tool.summary}")
        return 0

    if args.command == "find":
        for tool in find_tools(args.keyword):
            print(f"{tool.id} | {tool.category} | {tool.summary}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
