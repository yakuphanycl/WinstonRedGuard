from __future__ import annotations

from typing import Dict


TOOL_KEYWORDS = {
    "cli",
    "tool",
    "linter",
    "formatter",
    "test",
    "testing",
    "dev",
    "build",
    "packaging",
    "automation",
    "workflow",
    "code quality",
}


def is_devtool(pkg: Dict) -> bool:
    """
    Very simple heuristic classifier for developer tools.
    pkg example:
    {
        "name": "pytest",
        "summary": "...",
        "keywords": "testing pytest"
    }
    """

    score = 0

    name = (pkg.get("name") or "").lower()
    summary = (pkg.get("summary") or "").lower()
    keywords = (pkg.get("keywords") or "").lower()

    # signal 1 — summary
    for word in TOOL_KEYWORDS:
        if word in summary:
            score += 1
            break

    # signal 2 — keywords
    for word in TOOL_KEYWORDS:
        if word in keywords:
            score += 1
            break

    # signal 3 — name patterns
    if any(word in name for word in ["cli", "lint", "test", "format", "build"]):
        score += 1

    return score >= 2