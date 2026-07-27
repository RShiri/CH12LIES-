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
5. **Visualizes** results in a Hebrew RTL dashboard: recent-checks feed with screenshots,
   a weighted per-channel **Lie Index (מדד שקר)**, and per-category truth/lie charts.

## Architecture — Virtual Agents

| Agent | Package | Role |
|---|---|---|
| Orchestrator | `orchestrator/` | Scheduling, pipeline sequencing, backfill, run ledger |
| Scraper | `scrapers/` | `BaseNewsScraper` ABC + `N12Scraper` (Playwright), 13/14 stubs, category gate |
| Fact-Checker | `factcheck/` | Claim extraction, web-grounded verification, structured Hebrew verdicts |
| Database | `database/` | Repository pattern over SQLAlchemy (SQLite/Postgres), Lie Index metrics |
| Dashboard | `dashboard/` | Hebrew RTL Streamlit app |

Shared contracts (Pydantic models, category/verdict labels, config) live in `common/`.

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
