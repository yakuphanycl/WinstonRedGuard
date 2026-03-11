from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import json
import os
from time import perf_counter
from typing import Any

import requests


DEFAULT_BACKEND = "default"
SCRAPLING_BACKEND = "scrapling"
BACKEND_ENV_VAR = "DEVTOOL_GENOME_FETCH_BACKEND"
OBSERVATION_VERSION = "0.1"


@dataclass
class FetchResult:
    observation_version: str
    run_id: str | None
    source_id: str | None
    backend_requested: str
    backend_used: str
    fallback_used: bool
    duration_ms: int
    success: bool
    error_type: str | None
    artifact_path: str | None
    status_code: int | None
    text: str
    json_data: Any | None = None
    response: Any | None = None
    exception: Exception | None = None


def _duration_ms(start: float) -> int:
    return max(0, int((perf_counter() - start) * 1000))


def _combine_error_type(primary: str | None, secondary: str | None) -> str | None:
    if primary and secondary:
        return f"{primary};{secondary}"
    return primary or secondary


def _normalize_backend(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == SCRAPLING_BACKEND:
        return SCRAPLING_BACKEND
    return DEFAULT_BACKEND


def _resolve_backend(backend_requested: str | None) -> str:
    if backend_requested is not None:
        return _normalize_backend(backend_requested)
    return _normalize_backend(os.getenv(BACKEND_ENV_VAR))


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    if isinstance(content, str):
        return content
    return ""


def _response_status(response: Any) -> int | None:
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    return None


def _parse_json_payload(response: Any, text: str, parse_json: bool) -> tuple[Any | None, str | None, Exception | None]:
    if not parse_json:
        return None, None, None
    try:
        if hasattr(response, "json") and callable(response.json):
            return response.json(), None, None
        return json.loads(text), None, None
    except (ValueError, TypeError) as exc:
        return None, type(exc).__name__, exc


def _build_default_result(
    url: str,
    *,
    timeout: int,
    parse_json: bool,
    started: float,
    requested: str,
    run_id: str | None,
    source_id: str | None,
    artifact_path: str | None,
    fallback_used: bool,
    prior_error_type: str | None = None,
) -> FetchResult:
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return FetchResult(
            observation_version=OBSERVATION_VERSION,
            run_id=run_id,
            source_id=source_id,
            backend_requested=requested,
            backend_used=DEFAULT_BACKEND,
            fallback_used=fallback_used,
            duration_ms=_duration_ms(started),
            success=False,
            error_type=_combine_error_type(prior_error_type, type(exc).__name__),
            artifact_path=artifact_path,
            status_code=None,
            text="",
            json_data=None,
            response=None,
            exception=exc,
        )

    text = _response_text(response)
    json_data, parse_error_type, parse_exception = _parse_json_payload(response, text, parse_json)
    error_type = _combine_error_type(prior_error_type, parse_error_type)

    return FetchResult(
        observation_version=OBSERVATION_VERSION,
        run_id=run_id,
        source_id=source_id,
        backend_requested=requested,
        backend_used=DEFAULT_BACKEND,
        fallback_used=fallback_used,
        duration_ms=_duration_ms(started),
        success=True,
        error_type=error_type,
        artifact_path=artifact_path,
        status_code=_response_status(response),
        text=text,
        json_data=json_data,
        response=response,
        exception=parse_exception,
    )


def _fetch_with_scrapling(url: str, *, timeout: int) -> Any:
    module = import_module("scrapling")

    if hasattr(module, "Fetcher"):
        fetcher = module.Fetcher()
        if hasattr(fetcher, "get") and callable(fetcher.get):
            return fetcher.get(url, timeout=timeout)

    if hasattr(module, "StaticFetcher"):
        fetcher = module.StaticFetcher()
        if hasattr(fetcher, "get") and callable(fetcher.get):
            return fetcher.get(url, timeout=timeout)

    if hasattr(module, "fetch") and callable(module.fetch):
        return module.fetch(url, timeout=timeout)

    if hasattr(module, "request") and callable(module.request):
        return module.request(url=url, method="GET", timeout=timeout)

    raise RuntimeError("Scrapling API is not supported by this pilot adapter")


def fetch_url(
    url: str,
    *,
    timeout: int = 10,
    backend_requested: str | None = None,
    run_id: str | None = None,
    source_id: str | None = None,
    artifact_path: str | None = None,
    parse_json: bool = False,
) -> FetchResult:
    requested = _resolve_backend(backend_requested)
    started = perf_counter()

    if requested == SCRAPLING_BACKEND:
        try:
            response = _fetch_with_scrapling(url, timeout=timeout)
            text = _response_text(response)
            json_data, parse_error_type, parse_exception = _parse_json_payload(response, text, parse_json)
            return FetchResult(
                observation_version=OBSERVATION_VERSION,
                run_id=run_id,
                source_id=source_id,
                backend_requested=requested,
                backend_used=SCRAPLING_BACKEND,
                fallback_used=False,
                duration_ms=_duration_ms(started),
                success=True,
                error_type=parse_error_type,
                artifact_path=artifact_path,
                status_code=_response_status(response),
                text=text,
                json_data=json_data,
                response=response,
                exception=parse_exception,
            )
        except ModuleNotFoundError as exc:
            prior_error = f"ScraplingImportError:{type(exc).__name__}"
            return _build_default_result(
                url,
                timeout=timeout,
                parse_json=parse_json,
                started=started,
                requested=requested,
                run_id=run_id,
                source_id=source_id,
                artifact_path=artifact_path,
                fallback_used=True,
                prior_error_type=prior_error,
            )
        except Exception as exc:
            prior_error = f"ScraplingRuntimeError:{type(exc).__name__}"
            return _build_default_result(
                url,
                timeout=timeout,
                parse_json=parse_json,
                started=started,
                requested=requested,
                run_id=run_id,
                source_id=source_id,
                artifact_path=artifact_path,
                fallback_used=True,
                prior_error_type=prior_error,
            )

    return _build_default_result(
        url,
        timeout=timeout,
        parse_json=parse_json,
        started=started,
        requested=requested,
        run_id=run_id,
        source_id=source_id,
        artifact_path=artifact_path,
        fallback_used=False,
    )
