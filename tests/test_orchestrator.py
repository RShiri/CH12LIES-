"""Orchestrator tests: sequencing, dedupe, and failure isolation."""
from __future__ import annotations

from pathlib import Path

import pytest

from common.labels import Category, Channel
from common.models import Article, ArticleStub, FactCheckResult
from database.repository import SQLiteRepository
from factcheck.agent import FactCheckFailed
from orchestrator.pipeline import PipelineOrchestrator
from scrapers.factory import ScraperFactory

HEBREW_EXPLANATION = (
    "ההסבר המלא נכתב בעברית ומפרט את הממצאים שהתקבלו מהמקורות החיצוניים שנבדקו."
)


def stub(n: int, category=Category.SECURITY) -> ArticleStub:
    return ArticleStub(
        channel=Channel.N12,
        category=category,
        url=f"https://www.mako.co.il/news-military/Article-{n}.htm",
        headline=f"כותרת מספר {n} לבדיקת עובדות",
    )


class FakeScraper:
    """Stands in for a Playwright scraper — records what the pipeline asked for."""

    def __init__(self, stubs, fail_on: set[int] | None = None, empty_on: set[int] | None = None):
        self.stubs = stubs
        self.fail_on = fail_on or set()
        self.empty_on = empty_on or set()
        self.fetched: list[str] = []
        self.backfilled = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def list_recent_articles(self, since=None, limit=50):
        return self.stubs[:limit]

    def backfill(self, since, limit=500):
        self.backfilled = True
        return self.stubs[:limit]

    def fetch_article(self, s: ArticleStub) -> Article:
        index = int(str(s.url).split("-")[-1].removesuffix(".htm"))
        self.fetched.append(str(s.url))
        if index in self.fail_on:
            raise RuntimeError("page load timed out")
        return Article(
            channel=s.channel,
            category=s.category,
            url=s.url,
            headline=s.headline,
            full_text="" if index in self.empty_on else "גוף הכתבה המלא לבדיקה.",
            screenshot_path=Path(f"data/screenshots/n12/{s.article_id}.png"),
        )


class FakeChecker:
    def __init__(self, fail_on: set[str] | None = None, crash_on: set[str] | None = None):
        self.fail_on = fail_on or set()
        self.crash_on = crash_on or set()
        self.checked: list[str] = []

    def check(self, article: Article) -> FactCheckResult:
        url = str(article.url)
        self.checked.append(url)
        if url in self.crash_on:
            raise ValueError("unexpected internal error")
        if url in self.fail_on:
            raise FactCheckFailed("no search results")
        return FactCheckResult(
            fact_check_status="False",
            explanation=HEBREW_EXPLANATION,
            sources=["https://source.example/1"],
        )


@pytest.fixture
def repo():
    return SQLiteRepository("sqlite:///:memory:")


@pytest.fixture
def wire(monkeypatch):
    """Point the ScraperFactory at a FakeScraper for the duration of a test."""

    def _wire(scraper):
        monkeypatch.setattr(ScraperFactory, "get_scraper", staticmethod(lambda *a, **k: scraper))
        return scraper

    return _wire


def test_full_run_persists_articles_and_verdicts(repo, wire):
    scraper = wire(FakeScraper([stub(1), stub(2)]))
    checker = FakeChecker()
    report = PipelineOrchestrator(repo, checker).run_once(["n12"])

    assert (report.discovered, report.scraped, report.checked, report.failed) == (2, 2, 2, 0)
    rows = repo.get_recent()
    assert len(rows) == 2
    assert all(r.fact_check_status == "False" for r in rows)
    assert all(r.explanation == HEBREW_EXPLANATION for r in rows)
    assert all(r.screenshot_path for r in rows)


def test_rerun_skips_already_checked_articles(repo, wire):
    scraper = wire(FakeScraper([stub(1), stub(2)]))
    checker = FakeChecker()
    orchestrator = PipelineOrchestrator(repo, checker)

    orchestrator.run_once(["n12"])
    second = orchestrator.run_once(["n12"])

    assert second.skipped_already_checked == 2
    assert second.checked == 0
    # The expensive stages never ran a second time.
    assert len(checker.checked) == 2
    assert len(scraper.fetched) == 2
    assert len(repo.get_recent()) == 2


def test_scrape_failure_isolated_to_one_article(repo, wire):
    wire(FakeScraper([stub(1), stub(2), stub(3)], fail_on={2}))
    report = PipelineOrchestrator(repo, FakeChecker()).run_once(["n12"])

    assert (report.scraped, report.checked, report.failed) == (2, 2, 1)
    assert len(repo.get_recent()) == 2


def test_empty_body_is_rejected_before_llm_cost(repo, wire):
    wire(FakeScraper([stub(1), stub(2)], empty_on={1}))
    checker = FakeChecker()
    report = PipelineOrchestrator(repo, checker).run_once(["n12"])

    assert report.failed == 1
    assert len(checker.checked) == 1  # the empty article never reached the fact-checker


def test_factcheck_failure_keeps_article_but_no_verdict(repo, wire):
    failing = "https://www.mako.co.il/news-military/Article-1.htm"
    wire(FakeScraper([stub(1), stub(2)]))
    report = PipelineOrchestrator(repo, FakeChecker(fail_on={failing})).run_once(["n12"])

    assert (report.scraped, report.checked, report.failed) == (2, 1, 1)
    assert len(repo.get_recent(checked_only=True)) == 1
    assert len(repo.get_recent(checked_only=False)) == 2
    # A failed article is retried on the next run rather than being skipped.
    assert not repo.is_processed(failing)


def test_unexpected_checker_crash_does_not_abort_the_run(repo, wire):
    crashing = "https://www.mako.co.il/news-military/Article-1.htm"
    wire(FakeScraper([stub(1), stub(2)]))
    report = PipelineOrchestrator(repo, FakeChecker(crash_on={crashing})).run_once(["n12"])

    assert report.checked == 1
    assert report.failed == 1


def test_channel_error_recorded_without_killing_other_channels(repo, monkeypatch):
    scraper = FakeScraper([stub(1)])

    def get_scraper(channel, **kwargs):
        if str(channel) == "channel13":
            raise NotImplementedError("Channel13Scraper is a stub")
        return scraper

    monkeypatch.setattr(ScraperFactory, "get_scraper", staticmethod(get_scraper))
    report = PipelineOrchestrator(repo, FakeChecker()).run_once(["channel13", "n12"])

    assert report.checked == 1
    assert len(report.errors) == 1
    assert "channel13" in report.errors[0]


def test_backfill_uses_the_backfill_path_and_respects_limit(repo, wire):
    scraper = wire(FakeScraper([stub(i) for i in range(1, 11)]))
    report = PipelineOrchestrator(repo, FakeChecker()).backfill(["n12"], days=30, limit=4)

    assert scraper.backfilled
    assert report.checked == 4


def test_limit_caps_articles_processed(repo, wire):
    wire(FakeScraper([stub(i) for i in range(1, 21)]))
    report = PipelineOrchestrator(repo, FakeChecker()).run_once(["n12"], limit=3)
    assert report.checked == 3


def test_report_summary_is_human_readable(repo, wire):
    wire(FakeScraper([stub(1)]))
    report = PipelineOrchestrator(repo, FakeChecker()).run_once(["n12"])
    assert "checked=1" in report.summary()
    assert "n12" in report.summary()
