# Israeli News Fact-Check Platform · מדד שקר

Automated fact-checking pipeline for Israeli news channels — Channel 12 (N12) first,
architected to scale to Channels 13 and 14 — with a fully Hebrew, RTL Streamlit dashboard.

## What it does

1. **Scrapes** headlines and articles from channel news sites (Playwright), capturing a
   screenshot of every article as evidence.
2. **Filters strictly** to five categories only — ביטחוני, בעולם, פוליטי, בחירות, כלכלה.
   Everything else (sports, entertainment, gossip, tech…) is discarded at the ingestion
   boundary and rejected again by a database CHECK constraint.
3. **Fact-checks** each article's central claims with an LLM grounded by a web-search API,
   producing a structured verdict (`True | Mostly True | Misleading | False`), a
   **Hebrew** explanation, and verified source URLs.
4. **Stores** everything in a relational DB (SQLite by default, PostgreSQL-ready).
5. **Visualizes** results in a fully Hebrew, right-to-left dashboard: a recent-checks feed
   with screenshots, a weighted per-channel **Lie Index (מדד שקר)**, per-category
   truth/lie charts, and an educational **"איך המערכת עובדת"** tab that explains the whole
   pipeline in plain Hebrew for a reader with no technical background.

## Architecture — Virtual Agents

| Agent | Package | Role |
|---|---|---|
| Orchestrator | `orchestrator/` | Scheduling, pipeline sequencing, backfill, run ledger |
| Scraper | `scrapers/` | `BaseNewsScraper` ABC + `N12Scraper` (Playwright), 13/14 stubs, category gate |
| Fact-Checker | `factcheck/` | Claim extraction, web-grounded verification, structured Hebrew verdicts |
| Database | `database/` | Repository pattern over SQLAlchemy (SQLite/Postgres), Lie Index metrics |
| Dashboard | `dashboard/` | Hebrew RTL Streamlit app |

Shared contracts (Pydantic models, category/verdict labels, config) live in `common/`.

## The dashboard

Four tabs, all in Hebrew:

| Tab | What it shows |
|---|---|
| פיד בדיקות | Recent checks — screenshot, headline, verdict badge, Hebrew explanation, source links, plus a table view |
| מדד שקר | Current Lie Index per channel and its trend over time |
| פילוח לפי נושא | Verdict distribution and problematic-share across the five categories |
| איך המערכת עובדת | Plain-Hebrew walkthrough of the pipeline, the four verdicts, how the index is calculated, and the system's limitations |

**RTL:** `dashboard/styles.py` flips the app container, sidebar, headings, widget
labels, tabs, metrics, tables and expanders, using CSS logical properties so
spacing mirrors correctly. Latin runs (URLs, dates) are wrapped in isolated
`dir="ltr"` spans so the bidi algorithm doesn't reorder them. Charts read
right-to-left: bars grow from the right-hand label axis and the y-axis sits on
the right.

**Colour:** the four verdicts use an ordered green→red ramp validated for
colour-vision deficiency against the light chart surface. Two steps fall below
3:1 contrast, so every chart carries direct value labels and the feed ships a
table view — no meaning rests on colour alone. The Streamlit theme is pinned to
light in `.streamlit/config.toml` so the validated palette is what renders;
re-validate before changing any hex in `dashboard/theme.py`.

## Setup

```bash
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env   # fill in ANTHROPIC_API_KEY, SEARCH_API_KEY
```

## Usage

```bash
python -m orchestrator.cli run --channels n12          # scrape + fact-check latest
python -m orchestrator.cli backfill --channels n12     # backfill past 30 days
streamlit run dashboard/app.py                         # Hebrew RTL dashboard
pytest                                                 # tests
```
