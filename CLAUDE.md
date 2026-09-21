# CLAUDE.md — NBA Europe Demand Plan (v0)

## What this project is
A one-day demand planning project for my Nike EMEA Business Planning internship
application. Question: how much extra basketball demand should Nike EMEA plan for
around the NBA Europe launch (2027–28), by country, and with what confidence?

Full plan with step-by-step checklist: @docs/project1_plan.md
Decisions made so far: @docs/decision_log.md

Audience: a business planning team that works in Excel, not code. Python is only
used to collect and clean data. The main deliverables are an Excel decision model
and a one-page memo. Keep code simple and readable. I need to explain the method,
assumptions and decisions, not individual lines of code.

## Stack and environment
- OS: [fill in] · Python: [fill in version] · virtual env in `.venv/`
- Libraries: pandas, duckdb, requests, matplotlib, scipy, openpyxl
- Activate env: `[fill in, e.g. source .venv/bin/activate]`
- Ask before installing any new package.

## Repo structure
- `data/raw/` — raw API downloads. NEVER modify or delete files here.
- `data/processed/` — cleaned outputs (parquet), always regenerable from raw
- `src/` — final reusable scripts (one per step)
- `notebooks/` — exploration only; working code moves to `src/`
- `outputs/` — charts, memo.md, plan.xlsx
- `docs/` — plan, decision_log.md, ai_log.md

## How to work with me
- Work on ONE step of the plan at a time. Say which step/checkbox we're on.
- Make small changes, run them, show me the output, then continue.
- After each completed step: remind me to tick the checkbox, add a decision_log
  entry if we made a choice, and commit.
- If a step is taking much longer than planned, stop and propose a scope cut.
- Keep explanations short. I'm working against a deadline today.

## Data rules (important)
- Never invent data, dates, prices, margins or Wikipedia article titles.
  If unsure, mark it `# TODO: verify` and tell me.
- All assumptions (conversion rate, markdown depth, scenario probabilities)
  live as named constants at the top of the relevant script, with a comment.
- Results are expressed as % above baseline plan, not units. We have no Nike
  sales data; don't imply we do.

## API etiquette
- Wikimedia API: always send a descriptive User-Agent header; add small delays.
- Google Trends: if rate-limited, stop after a few retries and tell me. Don't
  loop aggressively. Wikipedia is the fallback.
- Cache raw downloads to `data/raw/` so we never re-download unnecessarily.

## Code conventions
- Scripts runnable from repo root: `python src/<script>.py`
- Functions small and named clearly; docstrings on public functions
- Use pathlib for paths; no hard-coded absolute paths
- Charts: title, labelled axes, saved to `outputs/charts/` as PNG

## Git
- Commit after each completed step with message format: `Step N: <what was done>`
- Never commit `.venv/` or secrets. Keep `.gitignore` up to date.

## Excel model rules
- Python exports clean analog results to Excel; scenarios and the newsvendor
  decision are built in Excel with live formulas, not pasted values.
- One `Assumptions` tab holds every input (price, margin, markdown depth,
  conversion rate, scenario probabilities), clearly labelled.
- Changing an assumption must update the recommendation automatically.
- Readable by a planner without me: clear tab names, units, short notes.

## Definition of done (v0)
Data collection and analog scripts, charts, `outputs/plan.xlsx` as the working
decision model, `outputs/memo.md` (one page), README with limitations and
responsible-AI section.
