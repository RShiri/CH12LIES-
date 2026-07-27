"""Playwright integration test against local HTML fixtures.

Exercises the real browser path — link discovery, the category gate, article
text extraction and screenshot capture — without needing network access to a
live news site. Skipped automatically when Chromium is unavailable.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from common.labels import Category, Channel
from scrapers.base import BaseNewsScraper

FIXTURES = Path(__file__).parent / "fixtures"

playwright = pytest.importorskip("playwright.sync_api")


def _chromium_available() -> bool:
    import os

    kwargs = {"headless": True}
    if os.getenv("CHROMIUM_EXECUTABLE_PATH"):
        kwargs["executable_path"] = os.environ["CHROMIUM_EXECUTABLE_PATH"]
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch(**kwargs).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _chromium_available(), reason="chromium not installed")


@pytest.fixture(scope="module")
def fixture_site():
    """Serve tests/fixtures over HTTP so URLs pass the HttpUrl contract."""
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


class FixtureScraper(BaseNewsScraper):
    """N12-shaped scraper pointed at the local fixture site."""

    CHANNEL = Channel.N12
    SECTIONS: dict = {}
    SELECTORS = {
        "article_link": ["article a[href]"],
        "headline": ["article h1"],
        "body": ["div.article-body p"],
        "published": ["time[datetime]"],
        "screenshot_target": ["article"],
    }

    def __init__(self, base_url: str, **kwargs):
        super().__init__(**kwargs)
        self.SECTIONS = {Category.SECURITY: [f"{base_url}/section.html"]}

    def is_article_url(self, url: str) -> bool:
        return url.endswith((".htm", ".html"))

    def backfill_urls(self, since: date) -> list[str]:
        return list(self.SECTIONS[Category.SECURITY])


def test_section_scrape_applies_category_gate(fixture_site):
    with FixtureScraper(fixture_site, request_delay_seconds=0) as scraper:
        stubs = scraper.list_recent_articles()

    headlines = [s.headline for s in stubs]
    assert any("צה״ל תקף" in h for h in headlines)
    assert any("האינפלציה" in h for h in headlines)
    # Sports cross-promo link and the too-short headline are both dropped.
    assert not any("מכבי חיפה" in h for h in headlines)
    assert not any(h == "קצר" for h in headlines)
    assert len(stubs) == 2


def test_url_category_overrides_section_category(fixture_site):
    with FixtureScraper(fixture_site, request_delay_seconds=0) as scraper:
        stubs = scraper.list_recent_articles()

    by_headline = {s.headline: s.category for s in stubs}
    security = next(c for h, c in by_headline.items() if "צה״ל" in h)
    economy = next(c for h, c in by_headline.items() if "האינפלציה" in h)
    assert security is Category.SECURITY
    assert economy is Category.ECONOMY  # URL says economy, section said security


def test_fetch_article_extracts_text_and_screenshot(fixture_site, tmp_path):
    from common.models import ArticleStub

    stub = ArticleStub(
        channel=Channel.N12,
        category=Category.SECURITY,
        url=f"{fixture_site}/article.html",
        headline="placeholder",
    )
    with FixtureScraper(fixture_site, screenshot_dir=tmp_path, request_delay_seconds=0) as scraper:
        article = scraper.fetch_article(stub)

    assert "צה״ל תקף מטרות בדרום לבנון" in article.headline
    assert "רקטות" in article.full_text
    assert len(article.full_text) > 200
    assert article.published_at is not None and article.published_at.year == 2026
    assert article.screenshot_path is not None
    assert article.screenshot_path.exists()
    assert article.screenshot_path.stat().st_size > 1000  # a real PNG, not an empty file
