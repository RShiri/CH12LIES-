import pytest

from common.labels import Category, Channel
from scrapers.base import parse_datetime
from scrapers.category_filter import CategoryRejected, classify, is_allowed, require_category
from scrapers.channel13_scraper import Channel13Scraper
from scrapers.channel14_scraper import Channel14Scraper
from scrapers.factory import ScraperFactory
from scrapers.n12_scraper import N12Scraper


@pytest.mark.parametrize(
    "signal,expected",
    [
        ("https://www.mako.co.il/news-military/article-1.htm", Category.SECURITY),
        ("https://www.mako.co.il/news-world/article-2.htm", Category.WORLD),
        ("https://www.mako.co.il/news-politics/knesset-vote", Category.POLITICAL),
        ("https://www.mako.co.il/news-elections/kalpi-2026", Category.ELECTIONS),
        ("https://www.mako.co.il/news-money/markets", Category.ECONOMY),
        ("חדשות ביטחוני", Category.SECURITY),
        ("בחירות 2026", Category.ELECTIONS),
    ],
)
def test_classify_allowed(signal, expected):
    assert classify(signal) is expected


@pytest.mark.parametrize(
    "signal",
    [
        "https://www.mako.co.il/sports-football/goal",
        "https://www.mako.co.il/entertainment-celebs/gossip",
        "https://www.mako.co.il/tech-gadgets/new-phone",
        "https://www.mako.co.il/food-recipes/shakshuka",
        "https://www.mako.co.il/health-fitness/diet",
        "ספורט",
        "רכילות",
        "",
    ],
)
def test_classify_rejects_offtopic(signal):
    assert classify(signal) is None
    assert not is_allowed(signal)


def test_elections_beats_generic_politics():
    # A URL mentioning both must resolve to the more specific category.
    assert classify("/news-politics/elections-2026") is Category.ELECTIONS


def test_rejected_section_wins_over_allowed_word():
    # "sports coverage of the political scene" must still be rejected.
    assert classify("/sports/politics-of-football") is None


def test_require_category_raises():
    with pytest.raises(CategoryRejected):
        require_category("https://www.mako.co.il/sports-football/goal")


def test_factory_returns_right_classes():
    assert isinstance(ScraperFactory.get_scraper("n12"), N12Scraper)
    assert isinstance(ScraperFactory.get_scraper(Channel.CHANNEL13), Channel13Scraper)
    assert isinstance(ScraperFactory.get_scraper("channel14"), Channel14Scraper)
    assert set(ScraperFactory.available()) == {"n12", "channel13", "channel14"}


def test_factory_rejects_unknown_channel():
    with pytest.raises(ValueError, match="unknown channel"):
        ScraperFactory.get_scraper("channel99")


def test_stubs_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        Channel13Scraper().list_recent_articles()
    with pytest.raises(NotImplementedError):
        Channel14Scraper().list_recent_articles()


def test_n12_sections_cover_only_allowed_categories():
    assert set(N12Scraper.SECTIONS) == set(Category)


def test_n12_article_url_matching():
    s = N12Scraper()
    assert s.is_article_url("https://www.mako.co.il/news-military/Article-abc123.htm")
    assert not s.is_article_url("https://www.mako.co.il/news-military")
    assert not s.is_article_url("https://other-site.com/Article-abc.htm")


def test_resolve_category_drops_crosspromo_links():
    s = N12Scraper()
    # Linked from the security section, but the URL is a sports story.
    assert s._resolve_category("/sports-football/Article-1.htm", Category.SECURITY) is None
    # Neutral URL inherits the section it was found in.
    assert s._resolve_category("/Article-xyz.htm", Category.SECURITY) is Category.SECURITY
    # Explicit URL category overrides the section.
    assert s._resolve_category("/news-money/Article-1.htm", Category.SECURITY) is Category.ECONOMY


def test_backfill_urls_scale_with_window():
    from datetime import date, timedelta

    s = N12Scraper()
    week = s.backfill_urls(date.today() - timedelta(days=7))
    month = s.backfill_urls(date.today() - timedelta(days=30))
    assert len(month) > len(week)
    assert all(u.startswith("https://www.mako.co.il") for u in month)


def test_screenshot_path_layout():
    from datetime import datetime, timezone

    s = N12Scraper(screenshot_dir="data/screenshots")
    path = s.screenshot_path_for("abc123", datetime(2026, 7, 27, tzinfo=timezone.utc))
    assert path.as_posix() == "data/screenshots/n12/2026-07-27/abc123.png"


@pytest.mark.parametrize(
    "raw,year",
    [("2026-07-27T10:30:00Z", 2026), ("27/07/2026", 2026), ("garbage", None), (None, None)],
)
def test_parse_datetime(raw, year):
    result = parse_datetime(raw)
    assert (result.year if result else None) == year
