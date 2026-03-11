from __future__ import annotations

import re

POSITIVE_HINTS = [
    "test",
    "testing",
    "test runner",
    "linter",
    "lint",
    "formatter",
    "formatting",
    "type checker",
    "static typing",
    "static analysis",
    "pre-commit",
    "pre commit",
    "hook",
    "hooks",
    "automation",
    "task runner",
    "cli",
    "command line",
    "code quality",
]

NEGATIVE_HINTS = [
    "library",
    "sdk",
    "client library",
    "api client",
    "http client",
    "bindings",
    "wrapper",
    "orm",
    "web framework",
    "data structures",
    "data analysis",
    "time series",
    "statistics",
    "scientific",
]

KNOWN_DEVTOOLS = {
    "pytest",
    "ruff",
    "black",
    "mypy",
    "tox",
    "nox",
    "isort",
    "flake8",
    "pre-commit",
    "uv",
    "pipx",
    "poetry",
}


def contains_hint(text: str, hint: str) -> bool:
    pattern = r"\b" + re.escape(hint) + r"\b"
    return re.search(pattern, text) is not None


def score_devtool(pkg: dict) -> int:
    name = str(pkg.get("name", "")).lower()
    summary = str(pkg.get("summary", "")).lower()
    keywords = str(pkg.get("keywords", "")).lower()

    text = f"{name} {summary} {keywords}"

    score = 0

    if name in KNOWN_DEVTOOLS:
        score += 6

    for hint in POSITIVE_HINTS:
        if contains_hint(text, hint):
            score += 2

    for hint in NEGATIVE_HINTS:
        if contains_hint(text, hint):
            score -= 2

    return score


def is_devtool(pkg: dict) -> bool:
    return score_devtool(pkg) >= 2