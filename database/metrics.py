"""Lie Index (מדד שקר) and aggregate metrics.

LieIndex(channel) = Σ(verdict_weight × recency_weight) / Σ(recency_weight)

- verdict_weight comes from config (False=1.0 … True=0.0), so 0 means a fully
  truthful channel and 1 a channel whose checked claims were all false.
- recency_weight decays exponentially with article age (half-life in config),
  so recent behavior dominates the score.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from database.models import ArticleRecord

DEFAULT_WEIGHTS = {"True": 0.0, "Mostly True": 0.2, "Misleading": 0.6, "False": 1.0}


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class ChannelStats:
    channel: str
    lie_index: float | None  # None when the channel has no checked articles
    total_checked: int
    verdict_counts: dict[str, int]


def lie_index(
    records: list[ArticleRecord],
    weights: dict[str, float] | None = None,
    half_life_days: float = 14,
    now: datetime | None = None,
) -> float | None:
    weights = weights or DEFAULT_WEIGHTS
    now = now or datetime.now(timezone.utc)
    num = 0.0
    den = 0.0
    for rec in records:
        if rec.fact_check_status not in weights:
            continue
        age_days = max((now - _as_utc(rec.timestamp)).total_seconds() / 86400, 0.0)
        recency = math.pow(0.5, age_days / half_life_days)
        num += weights[rec.fact_check_status] * recency
        den += recency
    return round(num / den, 4) if den > 0 else None


def channel_stats(
    records: list[ArticleRecord],
    channel: str,
    weights: dict[str, float] | None = None,
    half_life_days: float = 14,
) -> ChannelStats:
    mine = [r for r in records if r.channel_name == channel and r.fact_check_status]
    counts: dict[str, int] = {}
    for r in mine:
        counts[r.fact_check_status] = counts.get(r.fact_check_status, 0) + 1
    return ChannelStats(
        channel=channel,
        lie_index=lie_index(mine, weights, half_life_days),
        total_checked=len(mine),
        verdict_counts=counts,
    )


def lie_index_timeseries(
    records: list[ArticleRecord],
    channel: str,
    start: date,
    end: date,
    window_days: int = 7,
    weights: dict[str, float] | None = None,
    half_life_days: float = 14,
) -> list[tuple[date, float | None]]:
    """Daily Lie Index over a trailing window — feeds the dashboard trend chart."""
    mine = [r for r in records if r.channel_name == channel and r.fact_check_status]
    points: list[tuple[date, float | None]] = []
    day = start
    while day <= end:
        day_end = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        window_start = day_end - timedelta(days=window_days)
        in_window = [r for r in mine if window_start <= _as_utc(r.timestamp) <= day_end]
        points.append((day, lie_index(in_window, weights, half_life_days, now=day_end)))
        day += timedelta(days=1)
    return points


def category_verdict_matrix(
    records: list[ArticleRecord], channel: str | None = None
) -> dict[str, dict[str, int]]:
    """{category: {verdict: count}} — feeds the stacked-bar category chart."""
    matrix: dict[str, dict[str, int]] = {}
    for r in records:
        if not r.fact_check_status:
            continue
        if channel and r.channel_name != channel:
            continue
        matrix.setdefault(r.category, {})
        matrix[r.category][r.fact_check_status] = (
            matrix[r.category].get(r.fact_check_status, 0) + 1
        )
    return matrix
