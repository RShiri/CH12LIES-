"""The strict five-category gate.

This is the ingestion boundary: anything that does not map to one of the five
allowed categories is dropped here and never reaches the fact-checker or the
database. Sports, entertainment, gossip, tech, food, health and lifestyle are
explicitly recognised as rejected so a mis-mapped URL fails loudly in the logs
rather than silently sliding into a wrong category.
"""
from __future__ import annotations

import re

from common.labels import Category

# URL-path / section fragments that map onto the five allowed categories.
# Ordered most-specific first: 'elections' must win over the generic 'politics'.
_CATEGORY_PATTERNS: list[tuple[Category, tuple[str, ...]]] = [
    (Category.ELECTIONS, ("election", "בחירות", "kalpi", "מערכת-בחירות")),
    (
        Category.SECURITY,
        ("military", "security", "defense", "idf", "ביטחוני", "ביטחון", "צבא", "מלחמה", "war", "gaza", "hamas"),
    ),
    (Category.WORLD, ("world", "international", "global", "בעולם", "חול", "abroad")),
    (
        Category.ECONOMY,
        ("econom", "money", "finance", "business", "markets", "כלכלה", "פיננס", "שוק-ההון", "צרכנות"),
    ),
    (
        Category.POLITICAL,
        ("politic", "knesset", "government", "coalition", "פוליטי", "כנסת", "ממשלה", "קואליציה", "law", "משפט"),
    ),
]

# Sections we know we must never ingest. Matching one is an explicit reject.
_REJECTED_PATTERNS: tuple[str, ...] = (
    "sport", "ספורט", "football", "basketball", "mundial",
    "entertainment", "בידור", "celebs", "gossip", "רכילות", "tv-shows", "realit",
    "tech", "טכנולוגיה", "gadget", "science", "מדע",
    "food", "אוכל", "recipe", "מתכון", "health", "בריאות", "fitness",
    "travel", "תיירות", "fashion", "אופנה", "lifestyle", "style",
    "culture", "תרבות", "music", "מוזיקה", "cinema", "קולנוע", "weather", "מזג-אוויר",
    "horoscope", "הורוסקופ", "cars", "רכב", "games", "משחקים",
)


class CategoryRejected(Exception):
    """Raised when content does not belong to one of the five allowed categories."""


def _normalise(text: str) -> str:
    return re.sub(r"[_\s]+", "-", text.strip().lower())


def classify(*signals: str | None) -> Category | None:
    """Map scrape-time signals (URL, section name, breadcrumb) to a category.

    Returns None when nothing matches or the content is from a rejected section,
    which the caller treats as "discard this article".
    """
    haystack = _normalise(" ".join(s for s in signals if s))
    if not haystack:
        return None

    if any(bad in haystack for bad in _REJECTED_PATTERNS):
        return None

    for category, patterns in _CATEGORY_PATTERNS:
        if any(p in haystack for p in patterns):
            return category
    return None


def is_allowed(*signals: str | None) -> bool:
    return classify(*signals) is not None


def require_category(*signals: str | None) -> Category:
    """Like `classify`, but raises instead of returning None."""
    category = classify(*signals)
    if category is None:
        raise CategoryRejected(f"no allowed category for signals: {signals!r}")
    return category
