from __future__ import annotations

import json

import pytest

from devtool_genome.collector.classifier import is_devtool, score_devtool
from devtool_genome.collector.fetch_backend import FetchResult
from devtool_genome.collector.metadata import fetch_pypi_metadata


CASES = {
    "pytest": True,
    "ruff": True,
    "black": True,
    "mypy": True,
    "tox": True,
    "nox": True,
    "pre-commit": True,
    "requests": False,
    "numpy": False,
    "pandas": False,
    "fastapi": False,
    "sqlalchemy": False,
    "httpx": False,
    "pydantic": False,
}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.text = json.dumps(payload)
        self.status_code = 200

    def json(self) -> dict:
        return self._payload


def _package_from_url(url: str) -> str:
    # https://pypi.org/pypi/<package>/json
    return url.split("/pypi/", 1)[1].split("/json", 1)[0]


@pytest.fixture
def no_network_metadata(monkeypatch):
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

    monkeypatch.setattr("devtool_genome.collector.metadata.fetch_url", fake_fetch_url)


def test_classifier_cases(no_network_metadata) -> None:
    for name, expected in CASES.items():
        meta = fetch_pypi_metadata(name)
        got = is_devtool(meta)

        assert got == expected, (
            f"{name=} "
            f"{score_devtool(meta)=} "
            f"{expected=} "
            f"{got=}"
        )
