"""Pydantic contracts passed between the virtual agents."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, field_validator

from common.labels import Category, Channel, Verdict


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()


class ArticleStub(BaseModel):
    """Minimal reference to an article discovered on a section page."""

    channel: Channel
    category: Category
    url: HttpUrl
    headline: str
    published_at: datetime | None = None

    @property
    def article_id(self) -> str:
        return url_hash(str(self.url))[:16]


class Article(BaseModel):
    """Fully fetched article, ready for fact-checking."""

    channel: Channel
    category: Category
    url: HttpUrl
    headline: str
    full_text: str
    published_at: datetime | None = None
    screenshot_path: Path | None = None

    @property
    def article_id(self) -> str:
        return url_hash(str(self.url))[:16]


HEBREW_MIN_RATIO = 0.5


def hebrew_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Hebrew letters."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    hebrew = sum(1 for c in letters if "֐" <= c <= "׿")
    return hebrew / len(letters)


class FactCheckResult(BaseModel):
    """Structured verdict returned by the Fact-Checker Agent."""

    fact_check_status: Verdict
    explanation: str = Field(min_length=20)
    sources: list[HttpUrl] = Field(min_length=1)

    @field_validator("explanation")
    @classmethod
    def explanation_must_be_hebrew(cls, v: str) -> str:
        if hebrew_ratio(v) < HEBREW_MIN_RATIO:
            raise ValueError(
                "explanation must be written in Hebrew "
                f"(hebrew ratio {hebrew_ratio(v):.2f} < {HEBREW_MIN_RATIO})"
            )
        return v
