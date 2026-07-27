"""Abstract base for all channel scrapers (Strategy pattern).

Subclasses declare *what* to scrape — section URLs and CSS selectors — while
this class owns *how*: browser lifecycle, screenshot capture, HTML parsing,
the category gate and the backfill date window. Adding Channel 13 or 14 is
therefore a matter of filling in `SECTIONS` and `SELECTORS`.
"""
from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from common.labels import Category, Channel
from common.logging import get_logger
from common.models import Article, ArticleStub
from scrapers.category_filter import classify

log = get_logger("scraper")


class SelectorSet(dict):
    """CSS selectors per role; each role holds a fallback chain tried in order."""


DEFAULT_SELECTORS: dict[str, list[str]] = {
    # Links to individual articles on a section page.
    "article_link": ["article a[href]", "h2 a[href]", "a.card[href]", "a[href*='/Article-']"],
    # Article page fields.
    "headline": ["h1", "header h1", "[itemprop='headline']"],
    "body": ["article p", "[itemprop='articleBody'] p", ".article-body p", "main p"],
    "published": ["time[datetime]", "[itemprop='datePublished']"],
    # Element captured in the screenshot; falls back to the full page.
    "screenshot_target": ["article", "main", "body"],
}


class BaseNewsScraper(ABC):
    """Contract every channel scraper implements."""

    #: Canonical channel identifier.
    CHANNEL: Channel
    #: Section pages to crawl, mapped to the category they belong to.
    SECTIONS: dict[Category, list[str]] = {}
    #: Per-role CSS selector fallback chains; merged over DEFAULT_SELECTORS.
    SELECTORS: dict[str, list[str]] = {}

    def __init__(
        self,
        screenshot_dir: Path | str = "data/screenshots",
        request_delay_seconds: float = 2.0,
        headless: bool = True,
    ):
        self.screenshot_dir = Path(screenshot_dir)
        self.request_delay_seconds = request_delay_seconds
        self.headless = headless
        self.selectors = {**DEFAULT_SELECTORS, **self.SELECTORS}
        self._browser = None
        self._playwright = None

    # -- browser lifecycle -------------------------------------------------

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        launch_kwargs: dict = {"headless": self.headless}
        # Deployments that pin their own Chromium build (containers, CI images)
        # point CHROMIUM_EXECUTABLE_PATH at it instead of letting Playwright
        # download a matching one.
        executable = os.getenv("CHROMIUM_EXECUTABLE_PATH")
        if executable:
            launch_kwargs["executable_path"] = executable
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = self._playwright = None

    def _new_page(self):
        if self._browser is None:
            raise RuntimeError("scraper must be used as a context manager (`with Scraper() as s:`)")
        context = self._browser.new_context(
            locale="he-IL",
            viewport={"width": 1280, "height": 1600},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
        )
        return context.new_page()

    # -- public API --------------------------------------------------------

    def list_recent_articles(self, since: date | None = None, limit: int = 50) -> list[ArticleStub]:
        """Discover articles across all sections, keeping only allowed categories."""
        since = since or (datetime.now(timezone.utc).date() - timedelta(days=1))
        stubs: list[ArticleStub] = []
        seen: set[str] = set()

        page = self._new_page()
        try:
            for category, urls in self.SECTIONS.items():
                for section_url in urls:
                    if len(stubs) >= limit:
                        break
                    try:
                        found = self._scrape_section(page, section_url, category)
                    except Exception as exc:
                        log.warning(
                            "section scrape failed", extra={"ctx": {"url": section_url, "error": str(exc)}}
                        )
                        continue
                    for stub in found:
                        key = str(stub.url)
                        if key in seen:
                            continue
                        seen.add(key)
                        stubs.append(stub)
                        if len(stubs) >= limit:
                            break
                    time.sleep(self.request_delay_seconds)
        finally:
            page.context.close()

        log.info("discovered articles", extra={"ctx": {"channel": self.CHANNEL.value, "count": len(stubs)}})
        return stubs[:limit]

    def fetch_article(self, stub: ArticleStub) -> Article:
        """Load an article page, extract its text, and capture a screenshot."""
        page = self._new_page()
        try:
            page.goto(str(stub.url), wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1500)

            headline = self._first_text(page, "headline") or stub.headline
            full_text = self._body_text(page)
            published = self._published_at(page) or stub.published_at
            screenshot = self._capture(page, stub.article_id)

            return Article(
                channel=self.CHANNEL,
                category=stub.category,
                url=stub.url,
                headline=headline,
                full_text=full_text,
                published_at=published,
                screenshot_path=screenshot,
            )
        finally:
            page.context.close()

    def screenshot_path_for(self, article_id: str, when: datetime | None = None) -> Path:
        day = (when or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        return self.screenshot_dir / self.CHANNEL.value / day / f"{article_id}.png"

    # -- extraction helpers (shared by every channel) ----------------------

    def _scrape_section(self, page, section_url: str, category: Category) -> list[ArticleStub]:
        page.goto(section_url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(1500)
        links = self._collect_links(page, section_url)

        stubs = []
        for href, text in links:
            resolved = self._resolve_category(href, category)
            if resolved is None:
                continue
            headline = (text or "").strip()
            if len(headline) < 8:
                continue
            try:
                stubs.append(
                    ArticleStub(
                        channel=self.CHANNEL, category=resolved, url=href, headline=headline
                    )
                )
            except Exception:
                continue
        return stubs

    def _resolve_category(self, href: str, section_category: Category) -> Category | None:
        """Decide an article's category from its own URL, falling back to its section.

        A URL that names a rejected section (sports, gossip, …) is dropped even
        when it was linked from an allowed section page — cross-promo links are
        the main way off-topic content leaks into a category feed.
        """
        from scrapers.category_filter import _REJECTED_PATTERNS, _normalise

        own = classify(href)
        if own is not None:
            return own
        if any(bad in _normalise(href) for bad in _REJECTED_PATTERNS):
            return None
        return section_category

    def _collect_links(self, page, base_url: str) -> list[tuple[str, str]]:
        from urllib.parse import urljoin

        results: list[tuple[str, str]] = []
        seen: set[str] = set()
        for selector in self.selectors["article_link"]:
            for el in page.query_selector_all(selector):
                href = el.get_attribute("href")
                if not href or href.startswith(("#", "javascript:", "mailto:")):
                    continue
                absolute = urljoin(base_url, href)
                if absolute in seen or not self.is_article_url(absolute):
                    continue
                seen.add(absolute)
                results.append((absolute, el.inner_text()))
        return results

    def is_article_url(self, url: str) -> bool:
        """Subclasses narrow this to their site's article-URL shape."""
        return url.startswith("http")

    def _first_text(self, page, role: str) -> str | None:
        for selector in self.selectors[role]:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        return None

    def _body_text(self, page) -> str:
        for selector in self.selectors["body"]:
            parts = [el.inner_text().strip() for el in page.query_selector_all(selector)]
            parts = [p for p in parts if len(p) > 30]
            if parts:
                return "\n\n".join(parts)[:20_000]
        return ""

    def _published_at(self, page) -> datetime | None:
        for selector in self.selectors["published"]:
            el = page.query_selector(selector)
            if not el:
                continue
            raw = el.get_attribute("datetime") or el.get_attribute("content") or el.inner_text()
            parsed = parse_datetime(raw)
            if parsed:
                return parsed
        return None

    def _capture(self, page, article_id: str) -> Path | None:
        path = self.screenshot_path_for(article_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            for selector in self.selectors["screenshot_target"]:
                el = page.query_selector(selector)
                if el:
                    el.screenshot(path=str(path))
                    return path
            page.screenshot(path=str(path), full_page=True)
            return path
        except Exception as exc:
            log.warning("screenshot failed", extra={"ctx": {"id": article_id, "error": str(exc)}})
            return None

    # -- backfill ----------------------------------------------------------

    @abstractmethod
    def backfill_urls(self, since: date) -> list[str]:
        """Section/archive URLs that expose articles back to `since`."""

    def backfill(self, since: date, limit: int = 500) -> list[ArticleStub]:
        """Walk archive pages to recover the past month of articles."""
        stubs: list[ArticleStub] = []
        seen: set[str] = set()
        page = self._new_page()
        try:
            for url in self.backfill_urls(since):
                if len(stubs) >= limit:
                    break
                category = classify(url)
                if category is None:
                    continue
                try:
                    found = self._scrape_section(page, url, category)
                except Exception as exc:
                    log.warning("backfill page failed", extra={"ctx": {"url": url, "error": str(exc)}})
                    continue
                for stub in found:
                    if str(stub.url) not in seen:
                        seen.add(str(stub.url))
                        stubs.append(stub)
                time.sleep(self.request_delay_seconds)
        finally:
            page.context.close()
        return stubs[:limit]


_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_DMY_RE = re.compile(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})")


def parse_datetime(raw: str | None) -> datetime | None:
    """Parse the date formats Israeli news sites emit (ISO, or DD/MM/YYYY)."""
    if not raw:
        return None
    raw = raw.strip()
    if _ISO_RE.match(raw):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    m = _DMY_RE.search(raw)
    if m:
        day, month, year = (int(g) for g in m.groups())
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None
