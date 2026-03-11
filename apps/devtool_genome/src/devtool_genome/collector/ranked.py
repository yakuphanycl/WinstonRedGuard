from __future__ import annotations

from dataclasses import dataclass

from devtool_genome.classifier import score_package
from devtool_genome.collector.fetch_backend import fetch_url
from devtool_genome.collector.watchlist import get_watchlist


@dataclass
class RankedToolCandidate:
    name: str
    score: int
    summary: str
    keywords: str


def fetch_pypi_metadata(package_name: str) -> dict:
    url = f"https://pypi.org/pypi/{package_name}/json"

    result = fetch_url(url, timeout=10, parse_json=True)
    if result.exception is not None:
        return {}

    if result.status_code != 200:
        return {}

    if not isinstance(result.json_data, dict):
        return {}

    payload = result.json_data
    info = payload.get("info", {})

    return {
        "name": info.get("name") or package_name,
        "summary": info.get("summary") or "",
        "keywords": info.get("keywords") or "",
    }


def collect_watchlist_ranked() -> list[RankedToolCandidate]:
    results: list[RankedToolCandidate] = []

    for package_name in get_watchlist():
        meta = fetch_pypi_metadata(package_name)

        if not meta:
            continue

        score = score_package(
            name=meta["name"],
            summary=meta["summary"],
            keywords=meta["keywords"],
        )

        results.append(
            RankedToolCandidate(
                name=meta["name"],
                score=score,
                summary=meta["summary"],
                keywords=meta["keywords"],
            )
        )

    results.sort(key=lambda item: item.score, reverse=True)
    return results
