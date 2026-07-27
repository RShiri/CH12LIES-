"""Dashboard tests — figure builders, labels and RTL helpers.

The Streamlit runtime is not exercised; everything here is the pure logic that
decides what the user actually sees.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from common.labels import (
    CATEGORY_HE,
    CHANNEL_HE,
    VERDICT_HE,
    Category,
    Channel,
    Verdict,
)
from dashboard.components import category_charts, feed, how_it_works, lie_index
from dashboard.i18n import UI
from dashboard.styles import RTL_CSS, category_badge, ltr, verdict_badge
from dashboard.theme import CATEGORY_ORDER, VERDICT_COLOR, VERDICT_ORDER, lie_index_color
from database.models import ArticleRecord

WEIGHTS = {"True": 0.0, "Mostly True": 0.2, "Misleading": 0.6, "False": 1.0}


def record(
    verdict="False",
    category="security",
    channel="n12",
    days_ago=1,
    headline="כותרת לדוגמה",
) -> ArticleRecord:
    return ArticleRecord(
        channel_name=channel,
        category=category,
        url="https://www.mako.co.il/news-military/Article-1.htm",
        url_hash="h",
        headline=headline,
        full_text="גוף הכתבה",
        fact_check_status=verdict,
        explanation="הסבר מפורט בעברית על ממצאי הבדיקה.",
        sources=["https://source.example/1"],
        screenshot_path="data/screenshots/n12/2026-07-27/abc.png",
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


SAMPLE = [
    record("True", "security"),
    record("False", "security"),
    record("Misleading", "economy"),
    record("Mostly True", "political"),
    record("False", "elections"),
]


# -- label coverage: catches an enum gaining a member without a UI label ------


def test_every_enum_member_has_a_hebrew_label():
    assert set(CATEGORY_HE) == set(Category)
    assert set(VERDICT_HE) == set(Verdict)
    assert set(CHANNEL_HE) == set(Channel)


def test_every_verdict_has_a_colour_and_a_position():
    assert set(VERDICT_COLOR) == set(Verdict)
    assert set(VERDICT_ORDER) == set(Verdict)
    assert set(CATEGORY_ORDER) == set(Category)


def test_every_verdict_is_explained_in_the_educational_tab():
    assert set(how_it_works.VERDICT_EXPLANATIONS) == set(Verdict)


def test_verdict_order_runs_from_true_to_false():
    assert VERDICT_ORDER[0] is Verdict.TRUE
    assert VERDICT_ORDER[-1] is Verdict.FALSE


# -- stacked category chart ---------------------------------------------------


def _matrix(records, channel=None):
    from database.metrics import category_verdict_matrix

    return category_verdict_matrix(records, channel=channel)


def test_stacked_figure_has_one_trace_per_verdict_named_in_hebrew():
    figure = category_charts.build_stacked_figure(_matrix(SAMPLE))
    names = [trace.name for trace in figure.data]
    assert names == [VERDICT_HE[v] for v in VERDICT_ORDER]


def test_stacked_figure_labels_categories_in_hebrew_not_slugs():
    figure = category_charts.build_stacked_figure(_matrix(SAMPLE))
    labels = set(figure.data[0].y)
    assert labels <= set(CATEGORY_HE.values())
    assert not labels & {"security", "economy", "political", "elections", "world"}


def test_stacked_figure_carries_direct_value_labels():
    # Two palette steps sit below 3:1 contrast, so labels are the required relief.
    figure = category_charts.build_stacked_figure(_matrix(SAMPLE))
    assert all(trace.text is not None for trace in figure.data)
    assert any(any(t for t in trace.text) for trace in figure.data)


def test_stacked_figure_counts_match_the_data():
    figure = category_charts.build_stacked_figure(_matrix(SAMPLE))
    by_name = {t.name: dict(zip(t.y, t.x)) for t in figure.data}
    assert by_name[VERDICT_HE[Verdict.FALSE]][CATEGORY_HE[Category.SECURITY]] == 1
    assert by_name[VERDICT_HE[Verdict.TRUE]][CATEGORY_HE[Category.SECURITY]] == 1


def test_yaxis_sits_on_the_right_for_rtl_reading():
    figure = category_charts.build_stacked_figure(_matrix(SAMPLE))
    assert figure.layout.yaxis.side == "right"


# -- problematic share --------------------------------------------------------


def test_problematic_share_maths():
    shares = category_charts.problematic_share(_matrix(SAMPLE))
    assert shares["security"] == 0.5  # one False out of two
    assert shares["economy"] == 1.0  # a single Misleading
    assert shares["political"] == 0.0  # a single Mostly True


def test_problematic_share_skips_empty_categories():
    assert category_charts.problematic_share({"security": {}}) == {}


def test_share_figure_is_percentage_scaled_and_grows_right_to_left():
    figure = category_charts.build_share_figure(_matrix(SAMPLE))
    # Reversed range: bars start at the right-hand label axis, as an RTL reader
    # expects, rather than growing away from their own labels.
    assert figure.layout.xaxis.range == (1, 0)
    assert figure.layout.xaxis.tickformat == ".0%"


def test_stacked_bars_also_grow_right_to_left():
    figure = category_charts.build_stacked_figure(_matrix(SAMPLE))
    assert figure.layout.xaxis.autorange == "reversed"


# -- lie index trend ----------------------------------------------------------


def test_trend_figure_has_one_line_per_channel():
    records = SAMPLE + [record("True", "world", channel="channel13")]
    figure = lie_index.build_trend_figure(records, WEIGHTS, half_life_days=14, days=14)
    assert {t.name for t in figure.data} == {
        CHANNEL_HE[Channel.N12],
        CHANNEL_HE[Channel.CHANNEL13],
    }


def test_trend_axis_is_pinned_so_channels_stay_comparable():
    figure = lie_index.build_trend_figure(SAMPLE, WEIGHTS, half_life_days=14, days=14)
    assert figure.layout.yaxis.range == (0, 1)
    assert figure.layout.yaxis.side == "right"


def test_trend_figure_survives_an_empty_dataset():
    figure = lie_index.build_trend_figure([], WEIGHTS, half_life_days=14, days=14)
    assert len(figure.data) == 0


def test_lie_index_colour_tracks_severity():
    assert lie_index_color(0.05) == VERDICT_COLOR[Verdict.TRUE]
    assert lie_index_color(0.95) == VERDICT_COLOR[Verdict.FALSE]
    assert lie_index_color(None) not in VERDICT_COLOR.values()


# -- feed ---------------------------------------------------------------------


def test_table_rows_are_hebrew_all_the_way_through():
    rows = feed.build_table_rows(SAMPLE)
    assert set(rows[0]) == {"כותרת", "ערוץ", "נושא", "דירוג", "תאריך"}
    values = " ".join(str(v) for row in rows for v in row.values())
    assert "ביטחוני" in values and "ערוץ 12" in values
    for slug in ("security", "economy", "Misleading", "Mostly True", "n12"):
        assert slug not in values


def test_table_rows_render_every_verdict_in_hebrew():
    rows = feed.build_table_rows(SAMPLE)
    assert {r["דירוג"] for r in rows} <= set(VERDICT_HE.values())


# -- RTL helpers --------------------------------------------------------------


def test_ltr_isolates_latin_runs():
    assert ltr("https://example.com/a") == '<span class="ltr">https://example.com/a</span>'


def test_badges_carry_a_text_label_not_just_colour():
    badge = verdict_badge(Verdict.FALSE, VERDICT_HE[Verdict.FALSE])
    assert VERDICT_COLOR[Verdict.FALSE] in badge
    assert "שקר" in badge
    assert "ביטחוני" in category_badge("ביטחוני")


@pytest.mark.parametrize(
    "rule",
    [
        "direction: rtl",
        "text-align: right",
        "unicode-bidi: isolate",
        # Logical properties, so spacing mirrors instead of needing an
        # explicit left/right variant per rule.
        "margin-inline-start",
        "padding-inline-start",
        "margin-block-end",
    ],
)
def test_stylesheet_covers_the_rtl_essentials(rule):
    assert rule in RTL_CSS


def test_stylesheet_flips_sidebar_and_widget_labels():
    assert '[data-testid="stSidebar"]' in RTL_CSS
    assert '[data-testid="stWidgetLabel"]' in RTL_CSS
    assert '[data-testid="stMetric"]' in RTL_CSS


# -- i18n / educational content ----------------------------------------------

HEBREW_RANGE = ("֐", "׿")


def _has_hebrew(text: str) -> bool:
    return any(HEBREW_RANGE[0] <= c <= HEBREW_RANGE[1] for c in text)


def test_all_ui_strings_are_hebrew():
    for key, value in UI.items():
        assert _has_hebrew(value), f"{key} is not Hebrew: {value!r}"


def test_educational_tab_covers_every_pipeline_stage():
    prose = " ".join(
        [how_it_works.INTRO, how_it_works.INDEX_BODY, how_it_works.INDEX_RECENCY]
        + [s["title"] + s["body"] for s in how_it_works.STEPS]
    )
    for topic in ("איסוף", "סינון", "בדיקת העובדות", "מדד השקר", "צילום מסך"):
        assert topic in prose


def test_educational_tab_states_its_limitations():
    assert len(how_it_works.LIMITS) >= 4
    assert all(_has_hebrew(item) for item in how_it_works.LIMITS)


def test_educational_prose_avoids_coding_jargon():
    prose = " ".join(s["body"] for s in how_it_works.STEPS) + how_it_works.INDEX_BODY
    for jargon in ("API", "SQL", "JSON", "LLM", "Python", "מסד נתונים רלציוני"):
        assert jargon not in prose


def test_paragraph_helper_collapses_source_indentation():
    html = how_it_works._paragraphs("שורה ראשונה\n        המשך שלה\n\nפסקה שנייה")
    assert html.count("<p>") == 2
    assert "        " not in html
