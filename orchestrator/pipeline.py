"""The Orchestrator Agent — sequences the pipeline and owns failure handling.

    Scraper → category gate → dedupe → Fact-Checker → Database

Every stage failure is recorded against the article's URL hash in the run
ledger, so a re-run resumes where the last one stopped instead of re-scraping
and re-paying for articles that already have verdicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from common.labels import Channel
from common.logging import get_logger
from common.models import Article, ArticleStub
from database.repository import ArticleRepository
from factcheck.agent import FactCheckerAgent, FactCheckFailed
from scrapers.factory import ScraperFactory

log = get_logger("orchestrator")


@dataclass
class RunReport:
    """What a single pipeline run did — printed by the CLI and logged."""

    channels: list[str] = field(default_factory=list)
    discovered: int = 0
    skipped_already_checked: int = 0
    scraped: int = 0
    checked: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"channels={','.join(self.channels)} discovered={self.discovered} "
            f"skipped={self.skipped_already_checked} scraped={self.scraped} "
            f"checked={self.checked} failed={self.failed}"
        )


class PipelineOrchestrator:
    def __init__(
        self,
        repository: ArticleRepository,
        fact_checker: FactCheckerAgent,
        screenshot_dir: str = "data/screenshots",
        request_delay_seconds: float = 2.0,
        max_articles_per_run: int = 50,
    ):
        self.repo = repository
        self.fact_checker = fact_checker
        self.screenshot_dir = screenshot_dir
        self.request_delay_seconds = request_delay_seconds
        self.max_articles_per_run = max_articles_per_run

    # -- entry points ------------------------------------------------------

    def run_once(self, channels: list[str], limit: int | None = None) -> RunReport:
        """Scrape and fact-check the latest articles for each channel."""
        return self._run(channels, since=date.today() - timedelta(days=1), limit=limit)

    def backfill(
        self, channels: list[str], days: int = 30, limit: int | None = None
    ) -> RunReport:
        """Recover the past `days` of coverage. Safe to re-run — already-checked
        articles are skipped before any scraping or LLM cost is incurred."""
        return self._run(
            channels, since=date.today() - timedelta(days=days), limit=limit, backfill=True
        )

    # -- implementation ----------------------------------------------------

    def _run(
        self,
        channels: list[str],
        since: date,
        limit: int | None = None,
        backfill: bool = False,
    ) -> RunReport:
        report = RunReport(channels=list(channels))
        cap = limit or self.max_articles_per_run

        for channel in channels:
            try:
                self._run_channel(channel, since, cap, backfill, report)
            except Exception as exc:
                message = f"{channel}: {exc}"
                report.errors.append(message)
                log.error("channel run failed", extra={"ctx": {"channel": channel, "error": str(exc)}})

        log.info("run complete", extra={"ctx": {"summary": report.summary()}})
        return report

    def _run_channel(
        self, channel: str, since: date, cap: int, backfill: bool, report: RunReport
    ) -> None:
        scraper = ScraperFactory.get_scraper(
            Channel(channel),
            screenshot_dir=self.screenshot_dir,
            request_delay_seconds=self.request_delay_seconds,
        )
        with scraper:
            stubs = (
                scraper.backfill(since=since, limit=cap)
                if backfill
                else scraper.list_recent_articles(since=since, limit=cap)
            )
            report.discovered += len(stubs)

            # Dedupe before fetching: skipping here avoids a page load, a
            # screenshot, a search round-trip and an LLM call per article.
            pending = [s for s in stubs if not self.repo.is_processed(str(s.url))]
            report.skipped_already_checked += len(stubs) - len(pending)

            for stub in pending[:cap]:
                self._process(scraper, stub, report)

    def _process(self, scraper, stub: ArticleStub, report: RunReport) -> None:
        url = str(stub.url)
        try:
            article = scraper.fetch_article(stub)
        except Exception as exc:
            report.failed += 1
            self.repo.record_failure(url, f"scrape: {exc}")
            log.warning("scrape failed", extra={"ctx": {"url": url, "error": str(exc)}})
            return

        if not article.full_text.strip():
            report.failed += 1
            self.repo.record_failure(url, "scrape: empty article body")
            return

        self.repo.save_article(article)
        report.scraped += 1

        try:
            result = self.fact_checker.check(article)
        except FactCheckFailed as exc:
            report.failed += 1
            self.repo.record_failure(url, f"factcheck: {exc}")
            log.warning("fact-check failed", extra={"ctx": {"url": url, "error": str(exc)}})
            return
        except Exception as exc:
            report.failed += 1
            self.repo.record_failure(url, f"factcheck-error: {exc}")
            log.error("fact-check crashed", extra={"ctx": {"url": url, "error": str(exc)}})
            return

        self.repo.save_fact_check(url, result)
        report.checked += 1
        log.info(
            "article checked",
            extra={
                "ctx": {
                    "url": url,
                    "category": article.category.value,
                    "status": result.fact_check_status.value,
                }
            },
        )


def build_orchestrator(settings) -> PipelineOrchestrator:
    """Assemble the pipeline from configuration — used by the CLI."""
    from database.repository import get_repository
    from factcheck.search_provider import get_search_provider

    return PipelineOrchestrator(
        repository=get_repository(settings.db_url),
        fact_checker=FactCheckerAgent(
            search_provider=get_search_provider(settings.search_provider, settings.search_api_key),
            api_key=settings.anthropic_api_key or None,
            model=settings.factcheck.model,
            max_search_results=settings.factcheck.max_search_results,
            max_retries=settings.factcheck.max_retries,
            effort=settings.factcheck.effort,
        ),
        screenshot_dir=settings.scraping.screenshot_dir,
        request_delay_seconds=settings.scraping.request_delay_seconds,
        max_articles_per_run=settings.scraping.max_articles_per_run,
    )
