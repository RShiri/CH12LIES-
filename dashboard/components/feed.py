"""The recent-checks feed: screenshot, headline, verdict, explanation, sources."""
from __future__ import annotations

from pathlib import Path

from common.labels import CATEGORY_HE, CHANNEL_HE, VERDICT_HE, Category, Channel, Verdict
from dashboard.i18n import UI
from dashboard.styles import category_badge, ltr, verdict_badge


def _channel_label(name: str) -> str:
    try:
        return CHANNEL_HE[Channel(name)]
    except ValueError:
        return name


def _category_label(slug: str) -> str:
    try:
        return CATEGORY_HE[Category(slug)]
    except ValueError:
        return slug


def _verdict_label(slug: str) -> str:
    return VERDICT_HE[Verdict(slug)]


def _sources_html(sources: list[str] | None) -> str:
    if not sources:
        return ""
    items = "".join(
        f'<li><a href="{u}" target="_blank" rel="noopener">{ltr(u)}</a></li>' for u in sources
    )
    return f'<div class="article-meta">{UI["feed_sources"]}:</div><ul class="source-list">{items}</ul>'


def render_card(st, record) -> None:
    """One article per bordered container.

    The whole card is a single `st.container(border=True)` so the screenshot and
    explanation sit inside the same box as the headline — building the border in
    raw HTML would close it before Streamlit's own columns render.
    """
    verdict = Verdict(record.fact_check_status)
    published = record.timestamp.strftime("%d/%m/%Y") if record.timestamp else ""

    with st.container(border=True):
        st.markdown(
            f'<div class="article-headline">{record.headline}</div>'
            f'<div class="article-meta">'
            f"{_channel_label(record.channel_name)} · {ltr(published)}"
            f"{category_badge(_category_label(record.category))}"
            f"{verdict_badge(verdict, _verdict_label(record.fact_check_status))}"
            f"</div>",
            unsafe_allow_html=True,
        )

        image_col, text_col = st.columns([1, 2])
        with image_col:
            path = Path(record.screenshot_path) if record.screenshot_path else None
            if path and path.exists():
                st.image(str(path), use_container_width=True)
            else:
                st.caption(UI["feed_no_screenshot"])
        with text_col:
            if record.explanation:
                st.markdown(
                    f'<div class="article-meta">{UI["feed_explanation"]}:</div>'
                    f'<div class="article-explanation">{record.explanation}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(_sources_html(record.sources), unsafe_allow_html=True)
            st.markdown(
                f'<div class="article-meta">'
                f'<a href="{record.url}" target="_blank" rel="noopener">'
                f'{UI["feed_open_article"]}</a></div>',
                unsafe_allow_html=True,
            )


def build_table_rows(records) -> list[dict]:
    """Accessible table view — the relief for chart colours below 3:1 contrast."""
    return [
        {
            "כותרת": r.headline,
            "ערוץ": _channel_label(r.channel_name),
            "נושא": _category_label(r.category),
            "דירוג": _verdict_label(r.fact_check_status),
            "תאריך": r.timestamp.strftime("%d/%m/%Y") if r.timestamp else "",
        }
        for r in records
    ]


def render(st, records) -> None:
    st.subheader(UI["feed_title"])
    if not records:
        st.info(UI["feed_empty"])
        return

    with st.expander(UI["feed_table_view"]):
        st.caption(UI["feed_table_hint"])
        st.dataframe(build_table_rows(records), use_container_width=True, hide_index=True)

    for record in records:
        render_card(st, record)
