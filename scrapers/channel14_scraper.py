"""Channel 14 (Now 14) scraper — stub. See channel13_scraper for the pattern."""
from __future__ import annotations

from datetime import date

from common.labels import Category, Channel
from scrapers.base import BaseNewsScraper

BASE = "https://www.now14.co.il"


class Channel14Scraper(BaseNewsScraper):
    CHANNEL = Channel.CHANNEL14

    # TODO: confirm live section paths before enabling this channel.
    SECTIONS: dict[Category, list[str]] = {}
    SELECTORS: dict[str, list[str]] = {}

    def is_article_url(self, url: str) -> bool:
        return url.startswith(BASE)

    def backfill_urls(self, since: date) -> list[str]:
        raise NotImplementedError("Channel14Scraper: backfill not implemented yet")

    def list_recent_articles(self, since: date | None = None, limit: int = 50):
        raise NotImplementedError(
            "Channel14Scraper is a stub — populate SECTIONS/SELECTORS to enable it"
        )
