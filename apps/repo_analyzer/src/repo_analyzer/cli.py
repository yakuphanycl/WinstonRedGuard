from __future__ import annotations

import sys
from pathlib import Path

from .core import check_apps, detect_apps


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]

    if len(sys.argv) == 1:
        try:
            apps = detect_apps(repo_root)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print("detected apps:")
        for name in apps:
            print(f"- {name}")
        return 0

    cmd = sys.argv[1]

    if cmd == "check":
        try:
            results = check_apps(repo_root)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print("repo health:")
        for name, status in results:
            print(f"- {name}: {status}")
        return 0

    print(f"unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())