from __future__ import annotations

from typing import Any

import requests

from devtool_genome.collector import fetch_backend
from devtool_genome.collector.fetch_backend import BACKEND_ENV_VAR, OBSERVATION_VERSION, fetch_url


class FakeResponse:
    def __init__(self, *, status_code: int = 200, text: str = "", payload: Any = None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def test_fetch_url_default_backend_success(monkeypatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert url == "https://example.com"
        assert timeout == 10
        return FakeResponse(status_code=200, text="ok", payload={"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url("https://example.com")

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "default"
    assert result.backend_used == "default"
    assert result.fallback_used is False
    assert result.success is True
    assert result.error_type is None
    assert result.run_id is None
    assert result.source_id is None
    assert result.artifact_path is None
    assert result.status_code == 200
    assert result.text == "ok"
    assert isinstance(result.duration_ms, int)
    assert result.duration_ms >= 0


def test_fetch_url_populates_error_evidence_on_request_failure(monkeypatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url("https://example.com", timeout=5)

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "default"
    assert result.backend_used == "default"
    assert result.fallback_used is False
    assert result.success is False
    assert result.status_code is None
    assert result.text == ""
    assert result.error_type == "Timeout"
    assert isinstance(result.duration_ms, int)
    assert result.duration_ms >= 0


def test_fetch_url_can_parse_json_when_requested(monkeypatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        return FakeResponse(status_code=200, text='{"name":"pytest"}', payload={"name": "pytest"})

    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url("https://example.com", parse_json=True)

    assert result.success is True
    assert result.error_type is None
    assert result.json_data == {"name": "pytest"}


def test_fetch_url_scrapling_success_path(monkeypatch) -> None:
    def fake_scrapling(url: str, *, timeout: int) -> FakeResponse:
        assert url == "https://example.com"
        assert timeout == 7
        return FakeResponse(status_code=200, text='{"name":"pytest"}', payload={"name": "pytest"})

    def should_not_call_requests(url: str, timeout: int) -> FakeResponse:
        raise AssertionError("requests.get should not be called on scrapling success path")

    monkeypatch.setattr(fetch_backend, "_fetch_with_scrapling", fake_scrapling)
    monkeypatch.setattr(requests, "get", should_not_call_requests)

    result = fetch_url("https://example.com", timeout=7, backend_requested="scrapling", parse_json=True)

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "scrapling"
    assert result.backend_used == "scrapling"
    assert result.fallback_used is False
    assert result.success is True
    assert result.error_type is None
    assert result.status_code == 200
    assert result.json_data == {"name": "pytest"}


def test_fetch_url_scrapling_import_failure_falls_back_to_default(monkeypatch) -> None:
    def fake_scrapling(url: str, *, timeout: int) -> FakeResponse:
        raise ModuleNotFoundError("scrapling is not installed")

    def fake_get(url: str, timeout: int) -> FakeResponse:
        return FakeResponse(status_code=200, text="ok", payload={"ok": True})

    monkeypatch.setattr(fetch_backend, "_fetch_with_scrapling", fake_scrapling)
    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url("https://example.com", backend_requested="scrapling")

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "scrapling"
    assert result.backend_used == "default"
    assert result.fallback_used is True
    assert result.success is True
    assert result.status_code == 200
    assert result.error_type == "ScraplingImportError:ModuleNotFoundError"


def test_fetch_url_scrapling_runtime_failure_falls_back_to_default(monkeypatch) -> None:
    def fake_scrapling(url: str, *, timeout: int) -> FakeResponse:
        raise RuntimeError("scrapling runtime failed")

    def fake_get(url: str, timeout: int) -> FakeResponse:
        return FakeResponse(status_code=200, text="ok", payload={"ok": True})

    monkeypatch.setattr(fetch_backend, "_fetch_with_scrapling", fake_scrapling)
    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url("https://example.com", backend_requested="scrapling")

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "scrapling"
    assert result.backend_used == "default"
    assert result.fallback_used is True
    assert result.success is True
    assert result.status_code == 200
    assert result.error_type == "ScraplingRuntimeError:RuntimeError"


def test_fetch_url_uses_env_backend_when_not_explicit(monkeypatch) -> None:
    def fake_scrapling(url: str, *, timeout: int) -> FakeResponse:
        return FakeResponse(status_code=200, text="ok", payload={"ok": True})

    def should_not_call_requests(url: str, timeout: int) -> FakeResponse:
        raise AssertionError("requests.get should not be called when env selects scrapling")

    monkeypatch.setenv(BACKEND_ENV_VAR, "scrapling")
    monkeypatch.setattr(fetch_backend, "_fetch_with_scrapling", fake_scrapling)
    monkeypatch.setattr(requests, "get", should_not_call_requests)

    result = fetch_url("https://example.com")

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "scrapling"
    assert result.backend_used == "scrapling"
    assert result.fallback_used is False
    assert result.success is True


def test_fetch_url_scrapling_and_fallback_both_fail(monkeypatch) -> None:
    def fake_scrapling(url: str, *, timeout: int) -> FakeResponse:
        raise RuntimeError("scrapling runtime failed")

    def fake_get(url: str, timeout: int) -> FakeResponse:
        raise requests.ConnectionError("default backend failed")

    monkeypatch.setattr(fetch_backend, "_fetch_with_scrapling", fake_scrapling)
    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url("https://example.com", backend_requested="scrapling")

    assert result.observation_version == OBSERVATION_VERSION
    assert result.backend_requested == "scrapling"
    assert result.backend_used == "default"
    assert result.fallback_used is True
    assert result.success is False
    assert result.status_code is None
    assert isinstance(result.duration_ms, int)
    assert result.duration_ms >= 0
    assert result.error_type is not None
    assert result.error_type.startswith("ScraplingRuntimeError:RuntimeError")
    assert result.error_type.endswith("ConnectionError")


def test_fetch_url_preserves_optional_identity_fields(monkeypatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        return FakeResponse(status_code=200, text="ok", payload={"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)

    result = fetch_url(
        "https://example.com",
        run_id="run-42",
        source_id="pypi-main",
        artifact_path="artifacts/acquisition/devtool_genome/run-42/fetch.json",
    )

    assert result.run_id == "run-42"
    assert result.source_id == "pypi-main"
    assert result.artifact_path == "artifacts/acquisition/devtool_genome/run-42/fetch.json"
