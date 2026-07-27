"""CLI tests — argument wiring and the status report's Hebrew rendering."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from common.config import get_settings
from database.models import ArticleRecord
from database.repository import SQLiteRepository
from orchestrator.cli import build_parser, cmd_status


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_URL", f"sqlite:///{tmp_path/'cli.sqlite3'}")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def seed(db_url: str) -> None:
    repo = SQLiteRepository(db_url)
    rows = [
        ("security", "False"),
        ("economy", "True"),
        ("elections", "Misleading"),
    ]
    with repo.session() as s:
        for i, (category, verdict) in enumerate(rows):
            s.add(
                ArticleRecord(
                    channel_name="n12",
                    category=category,
                    url=f"https://e.com/{i}",
                    url_hash=f"hash{i}",
                    headline="כותרת",
                    full_text="גוף",
                    fact_check_status=verdict,
                    explanation="הסבר בעברית",
                    sources=["https://source.example/1"],
                    timestamp=datetime.now(timezone.utc),
                )
            )
        s.commit()


def test_status_renders_hebrew_labels(settings, capsys):
    seed(settings.db_url)
    assert cmd_status(None, settings) == 0

    out = capsys.readouterr().out
    assert "fact-checked articles: 3" in out
    assert "n12: lie_index=" in out
    # Verdict and category names are rendered in Hebrew, not raw slugs.
    assert "שקר=1" in out and "אמת=1" in out and "מטעה=1" in out
    assert "ביטחוני=1" in out and "כלכלה=1" in out and "בחירות=1" in out
    assert "security" not in out and "elections" not in out


def test_status_on_empty_database(settings, capsys):
    assert cmd_status(None, settings) == 0
    assert "fact-checked articles: 0" in capsys.readouterr().out


def test_parser_defaults_and_options():
    parser = build_parser()

    run = parser.parse_args(["run", "--channels", "n12", "--limit", "5"])
    assert run.channels == ["n12"] and run.limit == 5

    backfill = parser.parse_args(["backfill"])
    assert backfill.days == 30 and backfill.channels is None

    assert parser.parse_args(["backfill", "--days", "7"]).days == 7


def test_parser_requires_a_command():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
