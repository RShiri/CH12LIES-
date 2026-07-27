"""Streamlit entrypoint — the Hebrew, right-to-left dashboard.

    streamlit run dashboard/app.py

Reads only through the Database Agent's repository and metrics layer; there is
no SQL in the UI.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# `streamlit run dashboard/app.py` puts dashboard/ on sys.path rather than the
# project root, so the sibling packages need to be made importable first.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from common.config import get_settings
from common.labels import CATEGORY_HE, CHANNEL_HE, VERDICT_HE, Category, Channel, Verdict
from dashboard import styles
from dashboard.components import category_charts, feed, how_it_works, lie_index
from dashboard.i18n import UI
from database.repository import get_repository

ALL = UI["filter_all"]


@st.cache_data(ttl=300, show_spinner=False)
def load_records(db_url: str, days: int):
    """Fetch checked articles. Cached so tab switches don't re-query."""
    repo = get_repository(db_url)
    return repo.get_checked_articles(since=date.today() - timedelta(days=days))


def _channel_label(name: str) -> str:
    try:
        return CHANNEL_HE[Channel(name)]
    except ValueError:
        return name


def sidebar_filters(records) -> dict:
    """Hebrew-labelled filters. Options come from what is actually in the data."""
    st.sidebar.header(UI["filters"])

    channels = sorted({r.channel_name for r in records})
    channel = st.sidebar.selectbox(
        UI["filter_channel"],
        [ALL] + channels,
        format_func=lambda v: v if v == ALL else _channel_label(v),
    )

    categories = sorted({r.category for r in records})
    category = st.sidebar.selectbox(
        UI["filter_category"],
        [ALL] + categories,
        format_func=lambda v: v if v == ALL else CATEGORY_HE[Category(v)],
    )

    verdicts = [v.value for v in Verdict if any(r.fact_check_status == v.value for r in records)]
    verdict = st.sidebar.selectbox(
        UI["filter_verdict"],
        [ALL] + verdicts,
        format_func=lambda v: v if v == ALL else VERDICT_HE[Verdict(v)],
    )

    limit = st.sidebar.slider(UI["filter_limit"], min_value=5, max_value=100, value=20, step=5)

    st.sidebar.divider()
    if st.sidebar.button(UI["refresh"], use_container_width=True):
        load_records.clear()
        st.rerun()

    return {"channel": channel, "category": category, "verdict": verdict, "limit": limit}


def apply_filters(records, filters: dict):
    selected = records
    if filters["channel"] != ALL:
        selected = [r for r in selected if r.channel_name == filters["channel"]]
    if filters["category"] != ALL:
        selected = [r for r in selected if r.category == filters["category"]]
    if filters["verdict"] != ALL:
        selected = [r for r in selected if r.fact_check_status == filters["verdict"]]
    return selected


def main() -> None:
    settings = get_settings()

    st.set_page_config(
        page_title=UI["page_title"],
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    # Must run before anything else renders, or the first paint is left-to-right.
    styles.inject(st)

    st.title(UI["app_title"])
    st.caption(UI["app_subtitle"])

    days = st.sidebar.slider(UI["filter_days"], min_value=7, max_value=180, value=30, step=7)
    records = load_records(settings.db_url, days)

    filters = sidebar_filters(records)
    filtered = apply_filters(records, filters)

    tab_feed, tab_index, tab_categories, tab_how = st.tabs(
        [UI["tab_feed"], UI["tab_index"], UI["tab_categories"], UI["tab_how"]]
    )

    with tab_feed:
        if not records:
            st.info(UI["feed_empty"])
            st.code("python -m orchestrator.cli run --channels n12", language="bash")
        else:
            feed.render(st, filtered[: filters["limit"]])

    with tab_index:
        lie_index.render(
            st,
            # The index describes a channel over time, so it ignores the
            # category and verdict filters — narrowing those would bias it.
            records if filters["channel"] == ALL
            else [r for r in records if r.channel_name == filters["channel"]],
            weights=settings.lie_index.weights,
            half_life_days=settings.lie_index.recency_half_life_days,
            days=days,
        )

    with tab_categories:
        category_charts.render(
            st,
            records,
            channel=None if filters["channel"] == ALL else filters["channel"],
        )

    with tab_how:
        how_it_works.render(st, weights=settings.lie_index.weights)


if __name__ == "__main__":
    main()
