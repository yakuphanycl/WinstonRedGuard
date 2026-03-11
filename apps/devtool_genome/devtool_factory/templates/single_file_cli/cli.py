import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="{{tool_name}}",
        description="{{description}}",
    )
    parser.add_argument("input", help="input value")
    args = parser.parse_args()
    print("{{tool_name}}:", args.input)


if __name__ == "__main__":
    main()
