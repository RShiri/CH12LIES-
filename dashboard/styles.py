"""Right-to-left styling for the Streamlit app.

Streamlit renders left-to-right by default, so the whole app is flipped here:
the container, sidebar, headings, widget labels, tables, metrics, expanders and
alerts. Layout uses CSS logical properties (`margin-inline-*`, `text-align:
start`) so padding and alignment mirror correctly rather than needing a
left/right variant each.

Latin runs — URLs, channel ids, numbers with units — are wrapped in `dir="ltr"`
spans with `unicode-bidi: isolate`, otherwise the bidi algorithm reorders them
against the surrounding Hebrew and punctuation jumps to the wrong end.
"""
from __future__ import annotations

from common.labels import Verdict
from dashboard.theme import (
    BASELINE,
    GRIDLINE,
    INK_MUTED,
    INK_PRIMARY,
    INK_SECONDARY,
    SURFACE,
    VERDICT_COLOR,
)

RTL_CSS = f"""
<style>
:root {{
    --surface: {SURFACE};
    --ink: {INK_PRIMARY};
    --ink-secondary: {INK_SECONDARY};
    --ink-muted: {INK_MUTED};
    --gridline: {GRIDLINE};
    --baseline: {BASELINE};
}}

/* ---- global direction -------------------------------------------------- */
html, body, [class*="css"], .stApp,
section.main, .block-container,
[data-testid="stAppViewContainer"],
[data-testid="stSidebar"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"] {{
    direction: rtl;
    text-align: right;
}}

body, .stApp {{
    font-family: "Segoe UI", "Arial Hebrew", Arial, sans-serif;
}}

/* Headings and body copy align to the start edge (right, under RTL). */
h1, h2, h3, h4, h5, h6, p, li, label, span, div {{
    text-align: start;
}}

h1, h2, h3 {{ color: var(--ink); letter-spacing: 0; }}

/* ---- widgets ----------------------------------------------------------- */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
.stRadio label, .stSelectbox label, .stMultiSelect label, .stSlider label {{
    direction: rtl;
    text-align: right;
    font-weight: 600;
}}

/* Selected chips in multiselects sit at the start edge. */
[data-baseweb="select"] > div, [data-baseweb="tag"] {{ direction: rtl; }}

/* Slider tick labels stay LTR — they are numbers. */
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"],
[data-testid="stTickBar"] {{ direction: ltr; }}

/* ---- tabs -------------------------------------------------------------- */
/* Streamlit has moved between data-baseweb and data-testid hooks across
   versions, so both are targeted rather than betting on one. */
[data-testid="stTabs"] [data-baseweb="tab-list"],
[data-testid="stTabs"] [role="tablist"] {{
    direction: rtl;
    gap: 0.5rem;
}}
[data-testid="stTabs"] [data-baseweb="tab"],
[data-testid="stTab"],
[role="tab"] {{
    direction: rtl;
    text-align: right;
    font-size: 1.02rem;
}}

/* ---- metrics ----------------------------------------------------------- */
[data-testid="stMetric"] {{
    direction: rtl;
    text-align: right;
    background: var(--surface);
    border: 1px solid var(--gridline);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
}}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {{
    direction: rtl;
    text-align: right;
    justify-content: flex-start;
}}

/* ---- tables & dataframes ----------------------------------------------- */
[data-testid="stDataFrame"], [data-testid="stTable"], .stDataFrame {{
    direction: rtl;
}}
[data-testid="stTable"] th, [data-testid="stTable"] td {{
    text-align: right;
}}

/* ---- expanders, alerts, captions --------------------------------------- */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] p,
[data-testid="stNotification"],
[data-testid="stCaptionContainer"] {{
    direction: rtl;
    text-align: right;
}}

/* ---- charts ------------------------------------------------------------ */
/* Plotly draws its own internal LTR text; only the wrapper is flipped so the
   figure sits correctly in the RTL column. */
[data-testid="stPlotlyChart"] {{ direction: ltr; }}

/* ---- feed cards -------------------------------------------------------- */
.article-card {{
    background: var(--surface);
    border: 1px solid var(--gridline);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-block-end: 1rem;
    direction: rtl;
    text-align: right;
}}
.article-headline {{
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--ink);
    margin-block-end: 0.35rem;
    line-height: 1.5;
}}
.article-meta {{
    color: var(--ink-muted);
    font-size: 0.88rem;
    margin-block-end: 0.6rem;
}}
.article-explanation {{
    color: var(--ink-secondary);
    line-height: 1.8;
    margin-block-start: 0.5rem;
}}

/* Badges carry a text label, never colour alone. */
.badge {{
    display: inline-block;
    border-radius: 999px;
    padding: 0.18rem 0.7rem;
    font-size: 0.85rem;
    font-weight: 700;
    margin-inline-start: 0.4rem;
    color: #fcfcfb;
}}
.badge-category {{
    background: transparent;
    color: var(--ink-secondary);
    border: 1px solid var(--baseline);
}}

/* Latin text embedded in Hebrew must not be reordered by the bidi algorithm. */
.ltr {{
    direction: ltr;
    unicode-bidi: isolate;
    display: inline-block;
}}

.source-list {{ margin: 0; padding-inline-start: 1.2rem; }}
.source-list li {{ margin-block-end: 0.25rem; }}

/* ---- explanatory tab --------------------------------------------------- */
.how-step {{
    background: var(--surface);
    border: 1px solid var(--gridline);
    border-inline-start: 4px solid var(--baseline);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-block-end: 0.9rem;
    direction: rtl;
    text-align: right;
    line-height: 1.85;
}}
.how-step h4 {{ margin: 0 0 0.5rem 0; color: var(--ink); }}
.how-note {{
    background: #f3f6fb;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    line-height: 1.85;
    direction: rtl;
    text-align: right;
}}
</style>
"""


def inject(st) -> None:
    """Apply the RTL stylesheet. Call once, immediately after set_page_config."""
    st.markdown(RTL_CSS, unsafe_allow_html=True)


def ltr(text: str) -> str:
    """Wrap a Latin/numeric run so it renders correctly inside Hebrew text."""
    return f'<span class="ltr">{text}</span>'


def verdict_badge(verdict: Verdict, label: str) -> str:
    return f'<span class="badge" style="background:{VERDICT_COLOR[verdict]}">{label}</span>'


def category_badge(label: str) -> str:
    return f'<span class="badge badge-category">{label}</span>'
