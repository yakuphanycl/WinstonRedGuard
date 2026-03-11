from __future__ import annotations

from devtool_genome.collector.fetch_backend import fetch_url


GITHUB_API = "https://api.github.com/repos/{repo}"


def fetch_repo(repo: str) -> dict | None:
    url = GITHUB_API.format(repo=repo)

    try:
        result = fetch_url(url, timeout=10, parse_json=True)
        if result.exception is not None:
            return None
        if result.status_code != 200:
            return None

        if not isinstance(result.json_data, dict):
            return None
        return result.json_data

    except Exception:
        return None
