"""SQLAlchemy ORM models.

The category and verdict CHECK constraints are defense-in-depth: the scraper's
category gate should never let a disallowed category through, but the database
refuses one regardless.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from common.labels import ALLOWED_CATEGORIES, ALLOWED_VERDICTS


def _in_clause(column: str, values: frozenset[str]) -> str:
    quoted = ", ".join(f"'{v}'" for v in sorted(values))
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArticleRecord(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    channel_name: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    headline: Mapped[str] = mapped_column(Text, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    fact_check_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(_in_clause("category", ALLOWED_CATEGORIES), name="ck_allowed_category"),
        CheckConstraint(
            f"fact_check_status IS NULL OR {_in_clause('fact_check_status', ALLOWED_VERDICTS)}",
            name="ck_allowed_verdict",
        ),
        Index("ix_articles_channel_ts", "channel_name", "timestamp"),
        Index("ix_articles_category", "category"),
    )


class RunLedger(Base):
    """One row per pipeline stage completed for an article — makes re-runs idempotent."""

    __tablename__ = "run_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # scraped | checked | failed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_ledger_hash_stage", "url_hash", "stage"),)
