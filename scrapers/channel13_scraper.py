"""Channel 13 (Reshet 13) scraper — stub.

Registered with the factory so the channel can be enabled in config.yaml the
moment SECTIONS and SELECTORS below are filled in. Everything else — browser
handling, screenshots, category gating, backfill — is inherited.
"""
from __future__ import annotations

from datetime import date

from common.labels import Category, Channel
from scrapers.base import BaseNewsScraper

BASE = "https://13tv.co.il"


class Channel13Scraper(BaseNewsScraper):
    CHANNEL = Channel.CHANNEL13

    # TODO: confirm live section paths before enabling this channel.
    SECTIONS: dict[Category, list[str]] = {}
    SELECTORS: dict[str, list[str]] = {}

    def is_article_url(self, url: str) -> bool:
        return url.startswith(BASE)

    def backfill_urls(self, since: date) -> list[str]:
        raise NotImplementedError("Channel13Scraper: backfill not implemented yet")

    def list_recent_articles(self, since: date | None = None, limit: int = 50):
        raise NotImplementedError(
            "Channel13Scraper is a stub — populate SECTIONS/SELECTORS to enable it"
        )
