"""Lie Index (מדד שקר): current score per channel plus a trend over time."""
from __future__ import annotations

from datetime import date, timedelta

import plotly.graph_objects as go

from common.labels import CHANNEL_HE, VERDICT_HE, Channel, Verdict
from dashboard.i18n import UI
from dashboard.theme import (
    BASELINE,
    CHANNEL_COLOR,
    GRIDLINE,
    INK_MUTED,
    VERDICT_ORDER,
    lie_index_color,
    rtl_layout,
)
from database.metrics import channel_stats, lie_index_timeseries


def _channel_label(name: str) -> str:
    try:
        return CHANNEL_HE[Channel(name)]
    except ValueError:
        return name


def render_scores(st, records, weights, half_life_days) -> None:
    """One stat tile per channel — the headline number, not a chart."""
    channels = sorted({r.channel_name for r in records})
    if not channels:
        st.info(UI["index_no_data"])
        return

    columns = st.columns(len(channels))
    for column, channel in zip(columns, channels):
        stats = channel_stats(records, channel, weights=weights, half_life_days=half_life_days)
        with column:
            score = "—" if stats.lie_index is None else f"{stats.lie_index:.2f}"
            colour = lie_index_color(stats.lie_index)
            st.markdown(
                f'<div style="background:#fcfcfb;border:1px solid {GRIDLINE};'
                f'border-radius:10px;padding:1rem 1.2rem;direction:rtl;text-align:right">'
                f'<div style="color:{INK_MUTED};font-size:0.9rem">{_channel_label(channel)}'
                f' — {UI["index_current"]}</div>'
                f'<div style="font-size:2.4rem;font-weight:700;color:{colour};line-height:1.2">'
                f'<span class="ltr">{score}</span></div>'
                f'<div style="color:{INK_MUTED};font-size:0.85rem">'
                f'{UI["index_checked"]}: <span class="ltr">{stats.total_checked}</span></div>'
                f"</div>",
                unsafe_allow_html=True,
            )


def build_trend_figure(records, weights, half_life_days, days: int = 30) -> go.Figure:
    """One line per channel, y pinned to 0–1 so channels stay comparable."""
    end = date.today()
    start = end - timedelta(days=days)
    figure = go.Figure()

    for channel in sorted({r.channel_name for r in records}):
        points = lie_index_timeseries(
            records, channel, start, end, weights=weights, half_life_days=half_life_days
        )
        plotted = [(d, v) for d, v in points if v is not None]
        if not plotted:
            continue
        figure.add_trace(
            go.Scatter(
                x=[d for d, _ in plotted],
                y=[v for _, v in plotted],
                mode="lines",
                name=_channel_label(channel),
                line={"width": 2, "color": CHANNEL_COLOR.get(channel, "#2a78d6")},
                hovertemplate="%{x|%d/%m/%Y}<br>מדד: %{y:.2f}<extra>%{fullData.name}</extra>",
            )
        )

    figure.update_layout(**rtl_layout(title={"text": UI["index_trend"], "x": 1, "xanchor": "right"}))
    figure.update_xaxes(
        title_text=UI["index_axis_time"],
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
        tickformat="%d/%m",
    )
    # Axis on the right so the scale sits at the start edge for an RTL reader.
    figure.update_yaxes(
        title_text=UI["index_axis"],
        range=[0, 1],
        side="right",
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
    )
    figure.update_layout(hovermode="x unified")
    return figure


def render(st, records, weights, half_life_days, days: int = 30) -> None:
    st.subheader(UI["index_title"])
    st.caption(
        f'{UI["index_scale_low"]} 0.00 ← → 1.00 {UI["index_scale_high"]} · '
        + " · ".join(
            f"{VERDICT_HE[v]}={weights.get(v.value, 0):g}" for v in VERDICT_ORDER
        )
    )
    if not records:
        st.info(UI["index_no_data"])
        return

    render_scores(st, records, weights, half_life_days)
    st.plotly_chart(
        build_trend_figure(records, weights, half_life_days, days), use_container_width=True
    )
