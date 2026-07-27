"""Channel 12 (N12 / mako) scraper.

Section URLs and selectors live in class attributes so a site redesign is a
config change, not a rewrite. `SECTIONS` covers only the five allowed
categories — there is deliberately no entry for sports, culture or lifestyle.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from common.labels import Category, Channel
from scrapers.base import BaseNewsScraper

BASE = "https://www.mako.co.il"


class N12Scraper(BaseNewsScraper):
    CHANNEL = Channel.N12

    SECTIONS = {
        Category.SECURITY: [f"{BASE}/news-military", f"{BASE}/news-israel"],
        Category.WORLD: [f"{BASE}/news-world"],
        Category.POLITICAL: [f"{BASE}/news-politics", f"{BASE}/news-law"],
        Category.ELECTIONS: [f"{BASE}/news-elections"],
        Category.ECONOMY: [f"{BASE}/news-money", f"{BASE}/finances-magazine"],
    }

    SELECTORS = {
        "article_link": [
            "a[href*='Article-']",
            "article a[href]",
            ".content-list a[href]",
            "h2 a[href]",
        ],
        "headline": ["h1.article-header-title", "article h1", "h1"],
        "body": [
            "div.article-body p",
            "[itemprop='articleBody'] p",
            "article p",
            "main p",
        ],
        "published": ["time[datetime]", "span.display-date", "[itemprop='datePublished']"],
        "screenshot_target": ["article", "div.article-body", "main", "body"],
    }

    _ARTICLE_URL = re.compile(r"/Article-[\w-]+\.htm|/news-[\w-]+/Article", re.IGNORECASE)

    def is_article_url(self, url: str) -> bool:
        return url.startswith(BASE) and bool(self._ARTICLE_URL.search(url))

    def backfill_urls(self, since: date) -> list[str]:
        """Paginated section pages reaching back to `since`.

        mako exposes older items through `?page=N` on each section; roughly one
        page per two days of coverage, so the depth is derived from the window.
        """
        days = max((date.today() - since).days, 1)
        pages = min(max(days // 2, 1), 30)
        urls: list[str] = []
        for section_urls in self.SECTIONS.values():
            for section in section_urls:
                urls.append(section)
                urls.extend(f"{section}?page={n}" for n in range(2, pages + 1))
        return urls


def default_since(days: int = 30) -> date:
    return date.today() - timedelta(days=days)
