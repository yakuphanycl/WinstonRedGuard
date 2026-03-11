from __future__ import annotations

import json

import pytest

from devtool_genome.collector.fetch_backend import FetchResult
from devtool_genome.collector.ranked import RankedToolCandidate, collect_watchlist_ranked


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.text = json.dumps(payload)
        self.status_code = 200

    def json(self) -> dict:
        return self._payload


def _package_from_url(url: str) -> str:
    return url.split("/pypi/", 1)[1].split("/json", 1)[0]


@pytest.fixture
def no_network_ranked(monkeypatch):
    def fake_fetch_url(
        url: str,
        *,
        timeout: int = 10,
        backend_requested: str | None = None,
        parse_json: bool = False,
    ) -> FetchResult:
        package_name = _package_from_url(url)
        payload = {"info": {"name": package_name, "summary": "", "keywords": ""}}
        response = _FakeResponse(payload)
        return FetchResult(
            observation_version="0.1",
            run_id=None,
            source_id=None,
            backend_requested=backend_requested or "default",
            backend_used="default",
            fallback_used=False,
            duration_ms=1,
            success=True,
            error_type=None,
            artifact_path=None,
            status_code=200,
            text=response.text,
            json_data=payload if parse_json else None,
            response=response,
            exception=None,
        )

    monkeypatch.setattr("devtool_genome.collector.ranked.fetch_url", fake_fetch_url)


def test_collect_watchlist_ranked_returns_candidates(no_network_ranked) -> None:
    results = collect_watchlist_ranked()

    assert isinstance(results, list)
    assert results, "Expected non-empty ranked results"
    assert all(isinstance(item, RankedToolCandidate) for item in results)


def test_collect_watchlist_ranked_is_sorted_desc(no_network_ranked) -> None:
    results = collect_watchlist_ranked()

    scores = [item.score for item in results]
    assert scores == sorted(scores, reverse=True)


def test_collect_watchlist_ranked_contains_known_tools(no_network_ranked) -> None:
    results = collect_watchlist_ranked()
    names = {item.name.lower() for item in results}

    assert "pytest" in names
    assert "ruff" in names
    assert "tox" in names


def test_collect_watchlist_ranked_top_scores_are_positive(no_network_ranked) -> None:
    results = collect_watchlist_ranked()

    top_five = results[:5]
    assert top_five, "Expected at least 5 results"
    assert all(item.score > 0 for item in top_five)
