# CLAUDE.md

## Project
NBA Europe demand plan. Question: how much extra basketball demand should Nike EMEA plan for around the NBA Europe launch (2027-28), in which countries, and how confident should it be?
Main deliverable: a memo a non-technical reader can follow (recommendation first). The repo is the appendix. Author: Razvan Mihaila.

## Environment
- Windows 11, Python 3.13, venv in `.venv` (PowerShell: `.venv\Scripts\Activate.ps1`)
- Stack: pandas, DuckDB, matplotlib, scipy, openpyxl
- Commit directly to `main`. No PRs. Do not touch files the prompt doesn't mention.

## Hard rules
- Never invent data, dates, article titles or sources. If unverifiable, write UNVERIFIED and flag it.
- Anything that needs a judgement call goes in `docs/decision_log.md` as one row: Date | Decision | Why. Keep it short.
- End every task with a short summary: files changed, key numbers, anything flagged.
- Out of scope: survey, Google Trends, Greece, seasonality check, AI log.

## Data decisions (already made)
- Source: Wikipedia pageviews only (user agent), 14 series = 7 languages x Basketball + NBA. Titles are canonical (see `data/raw/titles.csv`).
- Weekly = ISO weeks, Monday start. Partial first/last weeks dropped.
- Index: each series' 2019 average weekly views = 100.
- Gaps: runs of 1-2 missing days filled with 0. Runs of 3+ left NULL, week flagged `incomplete` (it/nba, July 2026).
- Outliers: daily views capped at 5x the trailing 8-week median. Capped days listed in `outputs/capped_days.csv`.
- Baseline: median of 8 pre-event weeks.
- Control: median uplift of all markets not exposed to the event (NL counts as exposed for the Paris Olympics). NL-only kept as a secondary check.
- Turkey is kept (2019 baseline is stable, ~270 views/wk).
- Jan 2020 is a confound (Kobe Bryant's death). Do not use it in baselines.

## Analysis framing
- 7 events in 2 groups, each event counted once:
  - NBA events (scenario inputs): Wembanyama draft 2023-06-22 (FR); NBA Paris Game 2025-01-23/25 (FR); NBA Berlin Game 2026-01-15 (DE); NBA London Game 2026-01-18 (UK).
  - National-team events (the ceiling, not scenario inputs): Paris 2024 Olympics 2024-07-27 to 08-11 (FR); FIBA World Cup 2023, final 2023-09-10 (DE); EuroBasket 2025, 2025-08-27 to 09-14 (TR).
  - Exposed market is fixed in advance (in brackets above), never inferred from the data.
- Metrics per event x country: peak uplift vs 8-week pre-event baseline, half-life (weeks to half of peak), persistence (uplift left 12 weeks after). Report net of control (country minus NL).
- Known confounds: Paris 2025 overlaps the Wembanyama effect; Berlin 2026 has the Wagner brothers; the Olympics carry a host halo.
- Results are expressed as % above the baseline demand plan, never as units. Interest is a proxy for attention, not sales; the interest-to-demand conversion is an explicit assumption and is tested at 2+ values.
- Limitations to state: a Wikipedia language edition is not a country (English, Spanish especially); no sustained European NBA league has existed.
