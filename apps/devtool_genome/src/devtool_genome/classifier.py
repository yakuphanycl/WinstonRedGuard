from __future__ import annotations

import re

POSITIVE_HINTS = [
    "test",
    "testing",
    "test runner",
    "code coverage",
    "coverage",
    "linter",
    "lint",
    "formatter",
    "formatting",
    "format",
    "type checker",
    "static typing",
    "static analysis",
    "pre-commit",
    "automation",
    "task runner",
    "cli",
    "command line",
    "command-line",
    "tool",
    "developer tool",
    "build frontend",
    "build tool",
    "package publishing",
    "publishing packages",
    "dependency management",
    "package management",
    "virtual environment",
    "environment builder",
    "isolated environments",
    "workflow",
    "hooks",
    "property-based testing",
]

NEGATIVE_HINTS = [
    "library",
    "sdk",
    "client library",
    "api client",
    "bindings",
    "wrapper",
    "orm",
    "web framework",
    "data structures",
    "array computing",
    "database abstraction library",
]

KNOWN_DEVTOOLS = {
    "pytest",
    "ruff",
    "black",
    "mypy",
    "tox",
    "nox",
    "pre-commit",
    "flake8",
    "isort",
    "coverage",
    "hypothesis",
    "pip-tools",
    "pipx",
    "poetry",
    "build",
    "twine",
    "virtualenv",
    "httpie",
    "click",
    "typer",
}

LONG_DIGIT_RUN_RE = re.compile(r"\d{4,}")
STARTS_WITH_MANY_DIGITS_RE = re.compile(r"^\d{2,}")
GROUP_PROJECT_RE = re.compile(
    r"(group\d+|testpip|hello|demo|exercise|exercicio|school|homework)",
    re.IGNORECASE,
)


def name_suspicion_score(name: str) -> int:
    n = name.strip().lower()
    penalty = 0

    digit_count = sum(ch.isdigit() for ch in n)

    if STARTS_WITH_MANY_DIGITS_RE.search(n):
        penalty -= 3

    if LONG_DIGIT_RUN_RE.search(n):
        penalty -= 4

    if digit_count >= 4:
        penalty -= 2

    compact = n.replace("-", "").replace("_", "").replace(".", "")
    if len(compact) >= 8 and compact.isalnum() and digit_count >= len(compact) // 2:
        penalty -= 3

    if GROUP_PROJECT_RE.search(n):
        penalty -= 3

    if len(n) <= 6 and digit_count >= 1:
        penalty -= 2

    return penalty


def score_package(name: str, summary: str = "", keywords: str = "") -> int:
    n = name.strip().lower()
    s = (summary or "").strip().lower()
    k = (keywords or "").strip().lower()

    text = " ".join([n, s, k]).strip()
    score = 0

    if n in KNOWN_DEVTOOLS:
        score += 10

    for hint in POSITIVE_HINTS:
        if hint in text:
            score += 2

    for hint in NEGATIVE_HINTS:
        if hint in text:
            score -= 2

    score += name_suspicion_score(name)

    return score


def looks_like_devtool(name: str, summary: str = "", keywords: str = "") -> bool:
    return score_package(name=name, summary=summary, keywords=keywords) >= 5