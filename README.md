# nba-europe-demand-plan

Demand planning for NBA's expansion into the European market: how much extra basketball category demand should Nike EMEA plan for around the NBA Europe launch (2027–28), using Wikipedia interest around comparable past events (NBA games and national-team success) as a proxy for attention. **Recommendation: plan for +6.5% to +13% above baseline basketball demand in all six host markets, and buy to the base case, not the high case.**

- Memo (start here): [outputs/memo.md](outputs/memo.md) · printable version: [outputs/memo.html](outputs/memo.html)
- Decision model: [outputs/plan.xlsx](outputs/plan.xlsx)

## How to reproduce

Run in order:

```powershell
python src/collect_wikipedia.py   # pulls raw Wikipedia pageviews
python src/process_interest.py    # cleans + aggregates to weekly interest index
python src/analogs.py             # event-study: uplift, half-life, persistence per event
python src/star_test.py           # star-vs-league attention check
python src/scenarios.py           # low/base/high demand scenarios
python src/newsvendor.py          # buy recommendation (gross margin vs. markdown risk)
```

## Data sources

- Wikipedia pageviews (basketball/NBA articles, 7 languages) — collected via `src/collect_wikipedia.py`
- FIBA, Men's Olympic Basketball Tournament Paris 2024
- NBA.com, Paris 2024 Olympic basketball schedule
- NBA, Paris Games 2025
- NBA.com, Berlin Game 2026 primer
- NBA.com, London Game 2026 preview
- Wikipedia, 2023 FIBA Basketball World Cup
- Wikipedia, EuroBasket 2025
- NBA.com, games in Europe 2026–2028 announcement
- SEC EDGAR, Nike 10-K FY2025 (gross margin)

## More detail

- Full method and results: [docs/methodology.md](docs/methodology.md)
- Every judgement call, with rationale: [docs/decision_log.md](docs/decision_log.md)

## Setup

Requires Python 3.13.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
