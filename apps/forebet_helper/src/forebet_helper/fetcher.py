from __future__ import annotations

import random
import time

import httpx

from .cache import SimpleFileCache
from .config import Settings


class ForebetFetcher:
    def __init__(self, settings: Settings, cache: SimpleFileCache) -> None:
        self.settings = settings
        self.cache = cache

    def fetch_html(self, url: str, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached = self.cache.get(url, self.settings.cache_ttl_seconds)
            if cached is not None:
                return cached

        time.sleep(random.uniform(self.settings.min_delay_seconds, self.settings.max_delay_seconds))

        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
        }
        with httpx.Client(timeout=self.settings.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text

        self.cache.set(url, html)
        return html
