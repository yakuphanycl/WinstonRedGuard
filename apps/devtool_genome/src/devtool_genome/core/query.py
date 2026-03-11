from __future__ import annotations

from typing import List

from devtool_genome.data.schema import ToolRecord
from devtool_genome.data.store import load_tools


def search_tools(query: str) -> List[ToolRecord]:
    q = query.lower().strip()
    tools = load_tools()

    results: List[ToolRecord] = []
    for t in tools:
        haystack = " ".join([
            t.id,
            t.name,
            t.category,
            t.summary,
            " ".join(t.tags),
        ]).lower()

        if q in haystack:
            results.append(t)

    return results