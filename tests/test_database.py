from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from common.models import Article, FactCheckResult
from database.metrics import (
    category_verdict_matrix,
    channel_stats,
    lie_index,
)
from database.models import ArticleRecord
from database.repository import SQLiteRepository


@pytest.fixture
def repo():
    return SQLiteRepository("sqlite:///:memory:")


def make_article(url="https://example.com/article-1", category="political") -> Article:
    return Article(
        channel="n12",
        category=category,
        url=url,
        headline="כותרת לדוגמה",
        full_text="גוף הכתבה המלא לדוגמה.",
    )


HEBREW_EXPLANATION = "ההסבר המלא לבדיקת העובדות נכתב בעברית וכולל פירוט של הממצאים."


def test_save_and_read_roundtrip(repo):
    repo.save_article(make_article())
    repo.save_fact_check(
        "https://example.com/article-1",
        FactCheckResult(
            fact_check_status="False",
            explanation=HEBREW_EXPLANATION,
            sources=["https://source.example/1"],
        ),
    )
    rows = repo.get_recent()
    assert len(rows) == 1
    assert rows[0].fact_check_status == "False"
    assert rows[0].explanation == HEBREW_EXPLANATION
    assert rows[0].sources == ["https://source.example/1"]


def test_duplicate_url_is_deduped(repo):
    repo.save_article(make_article())
    repo.save_article(make_article())
    assert len(repo.get_recent(checked_only=False)) == 1


def test_is_processed_lifecycle(repo):
    url = "https://example.com/article-1"
    assert not repo.is_processed(url)
    repo.save_article(make_article(url))
    assert not repo.is_processed(url)  # scraped but not checked
    repo.save_fact_check(
        url,
        FactCheckResult(
            fact_check_status="True",
            explanation=HEBREW_EXPLANATION,
            sources=["https://source.example/1"],
        ),
    )
    assert repo.is_processed(url)


def test_db_rejects_disallowed_category(repo):
    with repo.session() as s:
        s.add(
            ArticleRecord(
                channel_name="n12",
                category="sports",  # not one of the 5 allowed
                url="https://example.com/x",
                url_hash="x" * 64,
                headline="h",
                full_text="t",
            )
        )
        with pytest.raises(IntegrityError):
            s.commit()


def _rec(status: str, days_ago: float) -> ArticleRecord:
    return ArticleRecord(
        channel_name="n12",
        category="political",
        url="https://e.com",
        url_hash="h",
        headline="h",
        full_text="t",
        fact_check_status=status,
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_lie_index_extremes():
    assert lie_index([_rec("True", 0)]) == 0.0
    assert lie_index([_rec("False", 0)]) == 1.0
    assert lie_index([]) is None


def test_lie_index_recency_weighting():
    # A recent lie should weigh more than an old truth of equal count.
    recent_lie_old_truth = lie_index([_rec("False", 0), _rec("True", 28)], half_life_days=14)
    old_lie_recent_truth = lie_index([_rec("False", 28), _rec("True", 0)], half_life_days=14)
    assert recent_lie_old_truth > 0.5 > old_lie_recent_truth


def test_channel_stats_counts():
    records = [_rec("False", 1), _rec("False", 2), _rec("True", 3)]
    stats = channel_stats(records, "n12")
    assert stats.total_checked == 3
    assert stats.verdict_counts == {"False": 2, "True": 1}
    assert 0.5 < stats.lie_index <= 1.0


def test_category_verdict_matrix():
    records = [_rec("False", 1), _rec("True", 1)]
    records[1].category = "economy"
    matrix = category_verdict_matrix(records)
    assert matrix == {"political": {"False": 1}, "economy": {"True": 1}}
