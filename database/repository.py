"""Repository pattern over SQLAlchemy.

`ArticleRepository` is the only persistence surface the other agents see.
`SQLiteRepository` and `PostgresRepository` differ only in engine URL and
engine-specific tuning; all query logic lives in the shared base.
"""
from __future__ import annotations

from abc import ABC
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from common.labels import Category, Verdict
from common.models import Article, FactCheckResult, url_hash
from database.models import ArticleRecord, Base, RunLedger


class ArticleRepository(ABC):
    """Persistence API used by the Orchestrator and Dashboard agents."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    # -- writes ----------------------------------------------------------

    def save_article(self, article: Article) -> ArticleRecord:
        """Insert a scraped article; on duplicate URL, return the existing row."""
        h = url_hash(str(article.url))
        with self.session() as s:
            existing = s.scalar(select(ArticleRecord).where(ArticleRecord.url_hash == h))
            if existing:
                return existing
            rec = ArticleRecord(
                channel_name=article.channel.value,
                category=article.category.value,
                url=str(article.url),
                url_hash=h,
                headline=article.headline,
                full_text=article.full_text,
                screenshot_path=str(article.screenshot_path) if article.screenshot_path else None,
                published_at=article.published_at,
            )
            s.add(rec)
            s.add(RunLedger(url_hash=h, stage="scraped"))
            s.commit()
            s.refresh(rec)
            return rec

    def save_fact_check(self, article_url: str, result: FactCheckResult) -> None:
        h = url_hash(article_url)
        with self.session() as s:
            rec = s.scalar(select(ArticleRecord).where(ArticleRecord.url_hash == h))
            if rec is None:
                raise ValueError(f"no article for url {article_url}")
            rec.fact_check_status = result.fact_check_status.value
            rec.explanation = result.explanation
            rec.sources = [str(u) for u in result.sources]
            rec.checked_at = datetime.now(timezone.utc)
            s.add(RunLedger(url_hash=h, stage="checked"))
            s.commit()

    def record_failure(self, article_url: str, detail: str) -> None:
        with self.session() as s:
            s.add(RunLedger(url_hash=url_hash(article_url), stage="failed", detail=detail))
            s.commit()

    # -- reads -----------------------------------------------------------

    def is_processed(self, article_url: str) -> bool:
        """True if the article has already been fact-checked (skip on re-runs)."""
        h = url_hash(article_url)
        with self.session() as s:
            rec = s.scalar(select(ArticleRecord).where(ArticleRecord.url_hash == h))
            return rec is not None and rec.fact_check_status is not None

    def get_recent(
        self,
        limit: int = 50,
        channel: str | None = None,
        category: Category | str | None = None,
        verdict: Verdict | str | None = None,
        since: date | None = None,
        checked_only: bool = True,
    ) -> list[ArticleRecord]:
        stmt = select(ArticleRecord).order_by(ArticleRecord.timestamp.desc()).limit(limit)
        if checked_only:
            stmt = stmt.where(ArticleRecord.fact_check_status.is_not(None))
        if channel:
            stmt = stmt.where(ArticleRecord.channel_name == str(channel))
        if category:
            stmt = stmt.where(ArticleRecord.category == str(category))
        if verdict:
            stmt = stmt.where(ArticleRecord.fact_check_status == str(verdict))
        if since:
            stmt = stmt.where(ArticleRecord.timestamp >= datetime(since.year, since.month, since.day, tzinfo=timezone.utc))
        with self.session() as s:
            return list(s.scalars(stmt))

    def get_checked_articles(self, since: date | None = None) -> list[ArticleRecord]:
        """All fact-checked rows — input for metrics/aggregations."""
        return self.get_recent(limit=100_000, since=since, checked_only=True)


class SQLiteRepository(ArticleRepository):
    def __init__(self, db_url: str = "sqlite:///data/db.sqlite3"):
        if db_url.startswith("sqlite:///"):
            db_path = db_url.removeprefix("sqlite:///")
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(create_engine(db_url))
        self.create_schema()


class PostgresRepository(ArticleRepository):
    def __init__(self, db_url: str):
        super().__init__(create_engine(db_url, pool_pre_ping=True))
        self.create_schema()


def get_repository(db_url: str) -> ArticleRepository:
    """Engine-selecting factory — call sites never pick a concrete class."""
    if db_url.startswith("sqlite"):
        return SQLiteRepository(db_url)
    if db_url.startswith("postgresql"):
        return PostgresRepository(db_url)
    raise ValueError(f"unsupported DB_URL: {db_url}")
