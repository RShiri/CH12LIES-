"""Verdict distribution across the five covered categories."""
from __future__ import annotations

import plotly.graph_objects as go

from common.labels import CATEGORY_HE, VERDICT_HE, Category, Verdict
from dashboard.i18n import UI
from dashboard.theme import (
    BASELINE,
    GRIDLINE,
    SURFACE,
    VERDICT_COLOR,
    VERDICT_ORDER,
    lie_index_color,
    rtl_layout,
)
from database.metrics import category_verdict_matrix

PROBLEMATIC = (Verdict.MISLEADING, Verdict.FALSE)


def _ordered_categories(matrix: dict[str, dict[str, int]]) -> list[Category]:
    from dashboard.theme import CATEGORY_ORDER

    return [c for c in CATEGORY_ORDER if c.value in matrix]


def build_stacked_figure(matrix: dict[str, dict[str, int]]) -> go.Figure:
    """Horizontal stacked bars — one row per category, one segment per verdict."""
    categories = _ordered_categories(matrix)
    labels = [CATEGORY_HE[c] for c in categories]
    figure = go.Figure()

    for verdict in VERDICT_ORDER:
        values = [matrix[c.value].get(verdict.value, 0) for c in categories]
        figure.add_trace(
            go.Bar(
                y=labels,
                x=values,
                name=VERDICT_HE[verdict],
                orientation="h",
                marker={
                    "color": VERDICT_COLOR[verdict],
                    # 2px surface gap between adjacent segments.
                    "line": {"color": SURFACE, "width": 2},
                },
                # Direct value labels: the relief for segment colours below 3:1.
                text=[str(v) if v else "" for v in values],
                textposition="inside",
                insidetextanchor="middle",
                textfont={"color": "#fcfcfb", "size": 13},
                hovertemplate="%{y} · %{x} כתבות<extra>%{fullData.name}</extra>",
            )
        )

    figure.update_layout(
        **rtl_layout(
            barmode="stack",
            bargap=0.35,
            title={"text": UI["cat_title"], "x": 1, "xanchor": "right"},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "traceorder": "normal",
                "title": {"text": ""},
            },
        )
    )
    # Bars grow right-to-left so each one starts at its own label on the
    # right-hand axis, matching the reading direction.
    figure.update_xaxes(
        title_text=UI["cat_count_axis"],
        autorange="reversed",
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
    )
    figure.update_yaxes(side="right", linecolor=BASELINE, gridcolor="rgba(0,0,0,0)")
    return figure


def problematic_share(matrix: dict[str, dict[str, int]]) -> dict[str, float]:
    """Share of each category's checks that came back misleading or false."""
    shares: dict[str, float] = {}
    for slug, counts in matrix.items():
        total = sum(counts.values())
        if total:
            bad = sum(counts.get(v.value, 0) for v in PROBLEMATIC)
            shares[slug] = round(bad / total, 4)
    return shares


def build_share_figure(matrix: dict[str, dict[str, int]]) -> go.Figure:
    shares = problematic_share(matrix)
    categories = [c for c in _ordered_categories(matrix) if c.value in shares]
    values = [shares[c.value] for c in categories]

    figure = go.Figure(
        go.Bar(
            y=[CATEGORY_HE[c] for c in categories],
            x=values,
            orientation="h",
            marker={"color": [lie_index_color(v) for v in values]},
            # A zero-length bar has nothing to sit beside, so its label would
            # collide with the category name on the axis. The empty row already
            # reads as nought.
            text=[f"{v:.0%}" if v > 0 else "" for v in values],
            textposition="outside",
            # A 100% bar ends at the axis edge, so its label would be clipped
            # without this.
            cliponaxis=False,
            hovertemplate="%{y} · %{x:.0%}<extra></extra>",
        )
    )
    figure.update_layout(
        **rtl_layout(
            bargap=0.4,
            showlegend=False,
            margin={"l": 70, "r": 90, "t": 50, "b": 40},
            title={"text": UI["cat_share_title"], "x": 1, "xanchor": "right"},
        )
    )
    # Reversed range (1 → 0) so bars grow right-to-left from the label axis.
    figure.update_xaxes(
        title_text=UI["cat_share_axis"],
        range=[1, 0],
        tickformat=".0%",
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
    )
    figure.update_yaxes(side="right", linecolor=BASELINE, gridcolor="rgba(0,0,0,0)")
    return figure


def render(st, records, channel: str | None = None) -> None:
    st.subheader(UI["cat_title"])
    matrix = category_verdict_matrix(records, channel=channel)
    if not matrix:
        st.info(UI["cat_no_data"])
        return
    st.plotly_chart(build_stacked_figure(matrix), use_container_width=True)
    st.plotly_chart(build_share_figure(matrix), use_container_width=True)
