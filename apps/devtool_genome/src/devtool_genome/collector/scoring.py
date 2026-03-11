from __future__ import annotations

from typing import Dict

TOOL_KEYWORDS = [
    "cli",
    "tool",
    "tools",
    "lint",
    "format",
    "test",
    "runner",
    "build",
    "dev",
    "env",
    "hook",
    "scan",
    "check",
    "watch",
    "pack",
    "sync",
    "deploy",
]

GOOD_PREFIX = [
    "py",
]

GOOD_SUFFIX = [
    "cli",
    "tool",
    "tools",
    "kit",
]


def score_tool_name(name: str) -> int:
    n = name.lower()

    score = 0

    # keyword sinyali
    for kw in TOOL_KEYWORDS:
        if kw in n:
            score += 3

    # prefix sinyali
    for p in GOOD_PREFIX:
        if n.startswith(p):
            score += 1

    # suffix sinyali
    for s in GOOD_SUFFIX:
        if n.endswith(s):
            score += 2

    # okunabilir token sayısı
    tokens = n.replace("-", "_").split("_")

    if len(tokens) >= 2:
        score += 1

    # çok kısa isimler genelde kötü sinyal
    if len(n) <= 4:
        score -= 1

    return score


def score_candidates(names):
    results = []

    for n in names:
        score = score_tool_name(n)

        results.append(
            {
                "name": n,
                "score": score,
            }
        )

    return sorted(results, key=lambda x: x["score"], reverse=True)