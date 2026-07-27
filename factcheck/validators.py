"""Semantic checks applied to the model's structured output."""
from __future__ import annotations

from urllib.parse import urlsplit

from common.models import HEBREW_MIN_RATIO, FactCheckResult, hebrew_ratio
from factcheck.schemas import LLMVerdict


class VerdictRejected(Exception):
    """The model's output violated a semantic rule; the reason feeds the retry prompt."""


def _canonical(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}"


def validate_verdict(verdict: LLMVerdict, allowed_urls: list[str]) -> FactCheckResult:
    """Convert a raw model verdict into a trusted FactCheckResult.

    Raises VerdictRejected with a Hebrew-readable reason when the explanation
    isn't Hebrew or a cited URL never appeared in the search results.
    """
    ratio = hebrew_ratio(verdict.explanation)
    if ratio < HEBREW_MIN_RATIO:
        raise VerdictRejected(
            f"ההסבר לא נכתב בעברית (שיעור אותיות עבריות: {ratio:.0%}). "
            "יש לכתוב את ההסבר כולו בעברית."
        )
    if len(verdict.explanation.strip()) < 80:
        raise VerdictRejected("ההסבר קצר מדי. נדרש פירוט של שתיים עד חמש פסקאות.")

    allowed = {_canonical(u) for u in allowed_urls}
    kept = [u for u in verdict.sources if _canonical(u) in allowed]
    invented = [u for u in verdict.sources if _canonical(u) not in allowed]
    if invented:
        raise VerdictRejected(
            "המקורות הבאים אינם מופיעים בתוצאות החיפוש שסופקו: "
            + ", ".join(invented[:3])
        )
    if not kept:
        raise VerdictRejected("לא צוינו מקורות. יש לצטט לפחות מקור אחד מתוך תוצאות החיפוש.")

    return FactCheckResult(
        fact_check_status=verdict.fact_check_status,
        explanation=verdict.explanation.strip(),
        sources=kept,
    )
