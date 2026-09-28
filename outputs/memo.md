## Why analog events

NBA Europe has no demand history: a sustained NBA-backed league has never operated in Europe. To estimate how demand may respond, this plan measures how public interest in basketball reacted to seven past events, split into two groups. For each one it records the size of the uplift, how quickly it faded and how much of it persisted.

- **NBA events** (scenario inputs) capture the league's own draw: a star-driven shock and three regular-season games on European soil.
- **National-team events** (the ceiling, not scenario inputs) show what a major national or international basketball success can do — a benchmark the NBA launch is not expected to reach on its own.

| Event | Date | Exposed market | Group |
|---|---|---|---|
| Wembanyama drafted #1 overall | 22 June 2023 | France | NBA event |
| NBA Paris Game | 23–25 January 2025 | France | NBA event |
| NBA Berlin Game | 15 January 2026 | Germany | NBA event |
| NBA London Game | 18 January 2026 | UK | NBA event |
| Paris 2024 Olympics | 27 July – 11 August 2024 | France, Netherlands | National-team event |
| FIBA World Cup 2023 | 25 August – 10 September 2023 | Germany | National-team event |
| EuroBasket 2025 | 27 August – 14 September 2025 | Turkey | National-team event |

## How the method was refined

Three issues surfaced while building this analysis, and are reflected in the numbers below.

**1. Wembanyama draft looked negative.** Its 8-week pre-event baseline averaged in an unrelated May 2023 French domestic-league spike, inflating the baseline so every later week looked like a decline. Fix: use the median of the 8 weeks, not the mean. Peak uplift: -48.8% → -44.2%.

**2. Paris Olympics barely beat its control.** The control market, the Netherlands, wasn't neutral — it won men's 3x3 Olympic gold, and Dutch interest stayed elevated through the back half of the Games, pointing to general Olympic interest rather than one medal moment. We reclassified the Netherlands as exposed, a call made after seeing the data rather than before. Fix: net France's peak against markets not exposed to the Games. Net peak uplift: -114.1% → +217.9%.

**3. One control market is fragile.** Relying on the Netherlands alone meant every event's net number rode on one country's noise. Fix: use the median uplift across all unexposed markets instead. For the Berlin NBA game, net peak uplift: -30.8% → +26.1%.

These corrections changed several net numbers substantially, but not the main finding: national-team success still produces far larger uplifts than any single NBA event.

## Results

Basketball topic, exposed market only.

| Event | Exposed market | Peak uplift | Half-life | Persistence (12w) | Net peak | Net persistence |
|---|---|---|---|---|---|---|
| Wembanyama draft | France | -44.2% | 1 week | -43.9% | -7.1% | -13.4% |
| NBA Paris Game | France | +7.3% | 1 week | -28.4% | -11.2% | -4.3% |
| NBA Berlin Game | Germany | +27.3% | 2 weeks | +6.4% | +26.1% | +17.3% |
| NBA London Game | UK | +26.9% | 3 weeks | -11.8% | +30.6% | -2.4% |
| Paris 2024 Olympics | France | +334.5% | 1 week | +102.7% | +217.9% | +106.3% |
| Paris 2024 Olympics | Netherlands | +402.4% | 1 week | -22.7% | +285.8% | -19.0% |
| FIBA World Cup 2023 | Germany | +268.2% | 1 week | +83.4% | +228.5% | -33.8% |
| EuroBasket 2025 | Turkey | +491.3% | 5 weeks | +323.7% | +443.6% | +270.2% |

National-team events show far larger and more durable uplifts than NBA-league events on every metric here — peak, net peak, and (mostly) persistence.

## Reading the results with care

Each analog carries a known bias, and the analysis corrects for it where possible:

- **The star effect.** The 2025 Paris games were Wembanyama's homecoming, and the 2026 Berlin game featured Germany's Franz and Moritz Wagner. Some of the local uplift therefore comes from national stars rather than from the NBA itself.
- **Olympic halo.** Interest during Paris 2024 was lifted by the Games as a whole; France's and the Netherlands' basketball success both contributed. This analog is best treated as an upper bound.
- **Seasonality.** The draft falls in the off-season, while the European games fall mid-season. All uplifts are measured against each market's own pre-event baseline, and net figures are measured against the median of markets not exposed to that event.

## Forward context

The NBA has already committed to regular-season games in Manchester and Paris in 2027 and in Berlin and Paris in 2028. Demand in these markets is therefore likely to be lifted by one-off games alongside the league launch. The plan accounts for this rather than attributing all uplift to the league.

---

### Sources

- NBA.com, 2023 NBA Draft No. 1 pick: https://www.nba.com/watch/video/victor-wembanyama-no-1-pick-spurs-2023-nba-draft
- FIBA, Men's Olympic Basketball Tournament Paris 2024: https://www.fiba.basketball/en/news/everything-you-need-to-know-mens-olympic-basketball-tournament-paris-2024
- NBA.com, Paris 2024 Olympic basketball schedule: https://www.nba.com/news/faq-paris-olympics-basketball-2024
- NBA, Paris Games 2025: https://nbaevents.nba.com/paris-games-2025
- NBA.com, games in Europe 2026–2028 announcement: https://www.nba.com/news/nba-announces-3-year-slate-of-games-in-europe-beginning-in-2026
- Wikipedia, 2023 FIBA Basketball World Cup (tournament dates verified 2023-08-25 to 2023-09-10): https://en.wikipedia.org/wiki/2023_FIBA_Basketball_World_Cup
