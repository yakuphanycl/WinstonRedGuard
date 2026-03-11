from __future__ import annotations

import random
import re

from devtool_genome.collector.fetch_backend import fetch_url


PYPI_SIMPLE = "https://pypi.org/simple/"


def discover_packages(limit: int = 100, seed: int = 42) -> list[str]:
    result = fetch_url(PYPI_SIMPLE, timeout=20)
    if result.exception is not None:
        raise result.exception
    if result.response is None:
        raise RuntimeError("fetch failed without response")
    result.response.raise_for_status()

    html = result.text
    names = re.findall(r">([^<]+)</a>", html)

    rng = random.Random(seed)
    rng.shuffle(names)

    return names[:limit]
