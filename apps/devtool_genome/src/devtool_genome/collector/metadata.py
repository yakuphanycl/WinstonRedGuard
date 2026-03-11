from __future__ import annotations

from devtool_genome.collector.fetch_backend import fetch_url


def fetch_pypi_metadata(package_name: str) -> dict:
    url = f"https://pypi.org/pypi/{package_name}/json"
    result = fetch_url(url, timeout=10, parse_json=True)
    if result.exception is not None:
        raise result.exception

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
        "home_page": info.get("home_page") or "",
        "requires_python": info.get("requires_python") or "",
        "classifiers": info.get("classifiers") or [],
    }
