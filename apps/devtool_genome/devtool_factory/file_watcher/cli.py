import argparse
from .core import run


def main():
    parser = argparse.ArgumentParser(
        prog="file_watcher",
        description="file_watcher CLI tool",
    )

    parser.add_argument(
        "input",
        help="input path or value",
    )

    args = parser.parse_args()

    run(args.input)


if __name__ == "__main__":
    main()
