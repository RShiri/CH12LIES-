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
   **Hebrew** explanation, and verified source URLs. A verdict may only cite URLs that
   actually came back from search, so hallucinated sources can't reach the database.
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

## Providers

Both the LLM and the search backend are pluggable — `factcheck/llm_provider.py` and
`factcheck/search_provider.py` each expose an ABC plus a name-keyed factory, so
switching vendors is a config change, not a code change.

| Role | Options | Default |
|---|---|---|
| LLM | `gemini`, `anthropic` | `gemini` — free tier via Google AI Studio |
| Search | `perplexity`, `tavily`, `serper` | `perplexity` |

Set the LLM in `config.yaml` (`factcheck.provider`) and search via `SEARCH_PROVIDER`
in `.env`. Each provider reads its own key (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`,
`SEARCH_API_KEY`).

**Cost:** Gemini's free tier is genuinely free but capped at 10 requests/minute and
250/day. The pipeline makes two LLM calls per article, so that's roughly 125 articles
a day; the client throttles itself to stay inside the limit and backs off on 429s
rather than dying mid-backfill. Perplexity's API is usage-billed — for a zero-cost
setup, switch `SEARCH_PROVIDER=tavily` and use Tavily's free tier.

## Setup

macOS / Linux:

```bash
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env     # fill in GEMINI_API_KEY and SEARCH_API_KEY
```

Windows (use `py` if `python` isn't on your PATH):

```cmd
py -m pip install -e ".[dev]"
py -m playwright install chromium
copy .env.example .env
notepad .env
```

## Usage

```bash
python -m orchestrator.cli run --channels n12                  # scrape + fact-check latest
python -m orchestrator.cli backfill --channels n12 --days 30   # backfill the past month
python -m orchestrator.cli status                              # what's in the database
streamlit run dashboard/app.py                                 # Hebrew RTL dashboard
pytest                                                         # tests
```

Start small to confirm your keys work before committing to a full backfill —
`--limit` caps how many articles a run processes:

```bash
python -m orchestrator.cli backfill --channels n12 --days 2 --limit 1
python -m orchestrator.cli status
```

On Windows, substitute `py -m` for `python -m` (and `py -m streamlit run …`).
