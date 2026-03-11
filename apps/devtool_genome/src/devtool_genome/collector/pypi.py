from __future__ import annotations

from devtool_genome.collector.fetch_backend import fetch_url


PYPI_URL = "https://pypi.org/pypi/{package}/json"


def fetch_metadata(package: str) -> dict | None:
    url = PYPI_URL.format(package=package)

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
