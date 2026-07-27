"""Schema the model is constrained to emit.

Deliberately permissive: it mirrors the JSON shape only. Semantic rules — the
explanation must be Hebrew, sources must come from the search results — are
checked afterwards in `validators.py` so a violation triggers a retry with
feedback instead of an exception the caller has to interpret.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LLMVerdict(BaseModel):
    """Raw structured output from the fact-checking model."""

    fact_check_status: Literal["True", "Mostly True", "Misleading", "False"] = Field(
        description="דירוג אמינות הטענה"
    )
    explanation: str = Field(description="הסבר מפורט בעברית בלבד, שתיים עד חמש פסקאות")
    sources: list[str] = Field(description="כתובות URL מתוך תוצאות החיפוש שסופקו בלבד")
