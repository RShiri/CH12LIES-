"""Chart palette and chrome.

The four verdicts are an ordered quality scale, so they get an ordered
green→red ramp rather than arbitrary categorical hues. These four steps were
validated as an adjacent set against the light chart surface: CVD separation
9.1, normal-vision separation 15.6. Two of them fall below 3:1 contrast on that
surface, which obligates visible labels — every chart here carries direct value
labels and the feed offers a table view, so no meaning rests on colour alone.

Re-validate before changing any hex.
"""
from __future__ import annotations

from common.labels import Category, Verdict

SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

#: Ordered truth→falsehood ramp.
VERDICT_COLOR: dict[Verdict, str] = {
    Verdict.TRUE: "#008300",
    Verdict.MOSTLY_TRUE: "#1baf7a",
    Verdict.MISLEADING: "#eda100",
    Verdict.FALSE: "#d03b3b",
}

#: Verdicts in the order they should stack and appear in legends.
VERDICT_ORDER: list[Verdict] = [
    Verdict.TRUE,
    Verdict.MOSTLY_TRUE,
    Verdict.MISLEADING,
    Verdict.FALSE,
]

CATEGORY_ORDER: list[Category] = [
    Category.SECURITY,
    Category.POLITICAL,
    Category.ELECTIONS,
    Category.ECONOMY,
    Category.WORLD,
]

#: Channels are one line each on the trend chart — categorical slots 1, 2, 4.
CHANNEL_COLOR: dict[str, str] = {
    "n12": "#2a78d6",
    "channel13": "#eb6834",
    "channel14": "#4a3aa7",
}

FONT_FAMILY = '"Segoe UI", "Arial Hebrew", Arial, sans-serif'


def lie_index_color(value: float | None) -> str:
    """Colour a Lie Index score on the same ramp the verdicts use."""
    if value is None:
        return INK_MUTED
    if value < 0.2:
        return VERDICT_COLOR[Verdict.TRUE]
    if value < 0.4:
        return VERDICT_COLOR[Verdict.MOSTLY_TRUE]
    if value < 0.6:
        return VERDICT_COLOR[Verdict.MISLEADING]
    return VERDICT_COLOR[Verdict.FALSE]


def rtl_layout(**overrides) -> dict:
    """Plotly layout defaults for a Hebrew right-to-left chart."""
    layout = {
        "font": {"family": FONT_FAMILY, "size": 14, "color": INK_SECONDARY},
        "paper_bgcolor": SURFACE,
        "plot_bgcolor": SURFACE,
        "margin": {"l": 20, "r": 90, "t": 50, "b": 40},
        "hoverlabel": {"font": {"family": FONT_FAMILY, "size": 14}, "align": "right"},
        # Legend reads right-to-left, above the plot.
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "traceorder": "normal",
        },
        "title": {"x": 1, "xanchor": "right", "font": {"size": 17, "color": INK_PRIMARY}},
    }
    layout.update(overrides)
    return layout
