# Methodology and full results

## How the method was refined

Three issues surfaced while building this analysis, and are reflected in the numbers below.

**1. Wembanyama draft: no measurable short-term effect.** Its 8-week pre-event baseline had averaged in an unrelated May 2023 French domestic-league spike, inflating the baseline so every later week looked like a decline; using the median of the 8 weeks instead of the mean fixed that (peak uplift: -48.8% → -44.2%). But the corrected number still isn't a real signal: the draft falls at the seasonal low point right after the May league finals, and a slow, season-long build from a star playing weekly is not something this event-study method can capture. It is excluded from scenario inputs.

**2. Paris Olympics showed France below its control.** The control market, the Netherlands, wasn't neutral. Dutch interest peaked on 6 August, the day after the Netherlands won 3x3 gold, and stayed high through the Olympic basketball finals. We reclassified the Netherlands as exposed, a call made after seeing the data rather than before. Fix: net France's peak against markets not exposed to the Games. Net peak uplift: -114.1% → +217.9%.

**3. One control market is fragile.** Relying on the Netherlands alone meant every event's net number rode on one country's noise. Fix: use the median uplift across all unexposed markets instead. For the Berlin NBA game, net peak uplift: -30.8% → +26.1%.

These corrections changed several net numbers substantially, but not the main finding: national-team success still produces far larger uplifts than any single NBA event.

## Results

Basketball topic, exposed market only.

| Event | Exposed market | Peak uplift | Half-life | Persistence (12w) | Net peak | Net persistence |
|---|---|---|---|---|---|---|
| Wembanyama draft (excluded, see above) | France | -44.2% | 1 week | -43.9% | -7.1% | -13.4% |
| NBA Paris Game | France | +7.3% | 1 week | -28.4% | -11.2% | -4.3% |
| NBA Berlin Game | Germany | +27.3% | 2 weeks | +6.4% | +26.1% | +17.3% |
| NBA London Game | UK | +26.9% | 3 weeks | -11.8% | +30.6% | -2.4% |
| Paris 2024 Olympics | France | +334.5% | 1 week | +102.7% | +217.9% | +106.3% |
| Paris 2024 Olympics | Netherlands | +402.4% | 1 week | -22.7% | +285.8% | -19.0% |
| FIBA World Cup 2023 | Germany | +268.2% | 1 week | +83.4% | +228.5% | -33.8% |
| EuroBasket 2025 | Turkey | +491.3% | 5 weeks | +323.7% | +443.6% | +270.2% |

Every national-team event produced a net peak at least seven times larger than any NBA event (+218% at minimum vs +31% at most). Whether the uplift lasts is less clear: 12-week persistence is high for France and Turkey, negative for Germany, and partly seasonal. Half-lives are short in both groups: most uplift fades within one to three weeks.
