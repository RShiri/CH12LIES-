import pytest
from pydantic import ValidationError

from common.labels import ALLOWED_CATEGORIES, CATEGORY_HE, VERDICT_HE, Category, Verdict
from common.models import Article, FactCheckResult, hebrew_ratio


def test_exactly_five_categories():
    assert ALLOWED_CATEGORIES == {"security", "world", "political", "elections", "economy"}
    assert set(CATEGORY_HE.values()) == {"ביטחוני", "בעולם", "פוליטי", "בחירות", "כלכלה"}


def test_verdict_hebrew_labels_complete():
    assert set(VERDICT_HE) == set(Verdict)


def test_article_rejects_bad_category():
    with pytest.raises(ValidationError):
        Article(
            channel="n12",
            category="sports",
            url="https://example.com/a",
            headline="כותרת",
            full_text="טקסט",
        )


def test_hebrew_ratio():
    assert hebrew_ratio("שלום עולם") == 1.0
    assert hebrew_ratio("hello world") == 0.0
    assert 0.4 < hebrew_ratio("שלום world") < 0.6


def test_factcheck_result_requires_hebrew_explanation():
    with pytest.raises(ValidationError, match="Hebrew"):
        FactCheckResult(
            fact_check_status="False",
            explanation="This explanation is written entirely in English which is not allowed.",
            sources=["https://example.com/proof"],
        )


def test_factcheck_result_accepts_hebrew():
    r = FactCheckResult(
        fact_check_status="Misleading",
        explanation="הטענה שהוצגה בכתבה מטעה מכיוון שהנתונים הרשמיים מראים תמונה שונה לחלוטין.",
        sources=["https://example.com/proof"],
    )
    assert r.fact_check_status is Verdict.MISLEADING


def test_factcheck_result_requires_sources():
    with pytest.raises(ValidationError):
        FactCheckResult(
            fact_check_status="True",
            explanation="הטענה נכונה ומגובה במקורות רשמיים של הלשכה המרכזית לסטטיסטיקה.",
            sources=[],
        )
