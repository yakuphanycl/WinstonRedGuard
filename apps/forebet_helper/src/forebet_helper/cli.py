from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .cache import SimpleFileCache
from .config import Settings
from .fetcher import ForebetFetcher
from .parser import parse_match_page
from .signals import to_match_signal
from .utils import dump_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forebet-helper",
        description="Personal-use Forebet signal extractor for a single match page.",
    )
    parser.add_argument("url", nargs="?", help="Forebet match page URL")
    parser.add_argument("--html-file", help="Read HTML from local file instead of the network")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and fetch again")
    parser.add_argument("--out", help="Write JSON output to the given path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.url and not args.html_file:
        parser.error("either a URL or --html-file must be provided")

    settings = Settings()

    if args.html_file:
        html_path = Path(args.html_file)
        html = html_path.read_text(encoding="utf-8")
        url = None
    else:
        cache = SimpleFileCache(settings.cache_dir)
        fetcher = ForebetFetcher(settings, cache)
        url = args.url
        html = fetcher.fetch_html(args.url, force_refresh=args.force_refresh)

    parsed = parse_match_page(html)
    signal = to_match_signal(parsed, url=url)
    payload = asdict(signal)

    if args.out:
        dump_json(Path(args.out), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
