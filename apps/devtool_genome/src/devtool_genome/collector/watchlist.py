from __future__ import annotations

# Curated developer tool candidates
# These are known tools from the Python developer ecosystem.
# Used for watchlist-based discovery experiments.

DEVTOOL_CANDIDATES = [
    "pytest",
    "pytest-cov",
    "tox",
    "nox",
    "ruff",
    "flake8",
    "black",
    "isort",
    "mypy",
    "pyright",
    "coverage",
    "hypothesis",
    "pre-commit",
    "pip-tools",
    "pipx",
    "poetry",
    "build",
    "twine",
    "virtualenv",
    "httpie",
    "click",
    "typer",
]


def get_watchlist() -> list[str]:
    """Return curated developer tool candidate list."""
    return DEVTOOL_CANDIDATES.copy()