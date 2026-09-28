"""Event-study analog analysis: uplift, half-life and persistence per event x country x topic."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WEEKLY_PARQUET = ROOT / "data" / "processed" / "weekly_interest.parquet"
TABLE_CSV = ROOT / "outputs" / "analogs_table.csv"
CHARTS_DIR = ROOT / "outputs" / "charts"

BASELINE_WEEKS = 8
PEAK_WINDOW_EXTRA_WEEKS = 4
HALF_LIFE_MAX_WEEKS = 26
PERSISTENCE_WEEKS = 12
NL_COUNTRY, NL_TOPIC = "Netherlands", "basketball"  # secondary NL-only check, kept for comparison

COUNTRIES = ["UK", "France", "Spain", "Italy", "Germany", "Turkey", "Netherlands"]
TOPICS = ["basketball", "nba"]

CHART_WEEKS_BEFORE = 8
CHART_WEEKS_AFTER = 16
EXPOSED_COLORS = ["#2a78d6", "#eb6834"]


@dataclass
class Event:
    event_id: str
    event_name: str
    group: str
    event_start: date
    event_end: date
    exposed_countries: tuple[str, ...]


# T2's tournament start date is verified: the 2023 FIBA Basketball World Cup ran
# 2023-08-25 to 2023-09-10 (confirmed via web search against Wikipedia/FIBA), which
# matches the fallback date given in the brief -- not left UNVERIFIED.
# T1: NL counts as exposed too -- it won men's 3x3 Olympic gold on 2024-08-05.
EVENTS = [
    Event("N1", "wembanyama_draft", "nba_event", date(2023, 6, 22), date(2023, 6, 22), ("France",)),
    Event("N2", "nba_paris_2025", "nba_event", date(2025, 1, 23), date(2025, 1, 25), ("France",)),
    Event("N3", "nba_berlin_2026", "nba_event", date(2026, 1, 15), date(2026, 1, 15), ("Germany",)),
    Event("N4", "nba_london_2026", "nba_event", date(2026, 1, 18), date(2026, 1, 18), ("UK",)),
    Event("T1", "paris_olympics", "national_team", date(2024, 7, 27), date(2024, 8, 11), ("France", "Netherlands")),
    Event("T2", "fiba_wc_2023", "national_team", date(2023, 8, 25), date(2023, 9, 10), ("Germany",)),
    Event("T3", "eurobasket_2025", "national_team", date(2025, 8, 27), date(2025, 9, 14), ("Turkey",)),
]


def load_weekly() -> pd.DataFrame:
    df = pd.read_parquet(WEEKLY_PARQUET)
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def week_start_of(d: date) -> pd.Timestamp:
    """The Monday (ISO week start) of the week containing d."""
    ts = pd.Timestamp(d)
    return ts - pd.Timedelta(days=ts.weekday())


def series_for(weekly: pd.DataFrame, country: str, topic: str) -> pd.DataFrame:
    return (
        weekly[(weekly["country"] == country) & (weekly["topic"] == topic)]
        .set_index("week_start")
        .sort_index()
    )


def safe_uplift(value: float | None, baseline: float | None) -> float:
    if value is None or pd.isna(value) or baseline is None or pd.isna(baseline) or baseline == 0:
        return float("nan")
    return value / baseline - 1


def compute_baseline(series: pd.DataFrame, event_week: pd.Timestamp) -> float:
    """Median index of the 8 full weeks before event_week, excluding incomplete weeks."""
    baseline_weeks = [event_week - pd.Timedelta(weeks=i) for i in range(1, BASELINE_WEEKS + 1)]
    rows = series.reindex(baseline_weeks)
    complete = rows[~rows["incomplete"].fillna(True)]
    valid = complete["index"].dropna()
    return valid.median() if len(valid) else float("nan")


def unexposed_countries(event: Event) -> list[str]:
    return [c for c in COUNTRIES if c not in event.exposed_countries]


def control_uplift_at(
    week: pd.Timestamp | None,
    event: Event,
    topic: str,
    series_map: dict[str, pd.DataFrame],
    baselines: dict[str, float],
) -> float:
    """Median uplift, at `week`, across markets NOT exposed to this event (same topic)."""
    if week is None:
        return float("nan")
    values = [
        safe_uplift(series_map[c]["index"].get(week), baselines[c])
        for c in unexposed_countries(event)
    ]
    values = [v for v in values if pd.notna(v)]
    return float(pd.Series(values).median()) if values else float("nan")


def compute_row(
    event: Event,
    country: str,
    topic: str,
    series_map: dict[str, pd.DataFrame],
    baselines: dict[str, float],
    nl_series: pd.DataFrame,
    nl_baseline: float,
) -> dict:
    series = series_map[country]
    baseline = baselines[country]
    event_week = week_start_of(event.event_start)
    end_week = week_start_of(event.event_end)

    peak_end_week = end_week + pd.Timedelta(weeks=PEAK_WINDOW_EXTRA_WEEKS)
    window_weeks = pd.date_range(event_week, peak_end_week, freq="7D")
    uplift_window = pd.Series(
        {wk: safe_uplift(series["index"].get(wk), baseline) for wk in window_weeks}
    )

    if uplift_window.notna().any():
        peak_week = uplift_window.idxmax()
        peak_uplift = uplift_window.loc[peak_week]
    else:
        peak_week, peak_uplift = None, float("nan")

    half_life_weeks = None
    if peak_week is not None and pd.notna(peak_uplift):
        threshold = peak_uplift / 2
        for w in range(1, HALF_LIFE_MAX_WEEKS + 1):
            up = safe_uplift(series["index"].get(peak_week + pd.Timedelta(weeks=w)), baseline)
            if pd.isna(up):
                continue
            if up < threshold:
                half_life_weeks = w
                break

    persistence_week = end_week + pd.Timedelta(weeks=PERSISTENCE_WEEKS)
    persistence_12w = safe_uplift(series["index"].get(persistence_week), baseline)

    def nl_uplift_at(week: pd.Timestamp | None) -> float:
        if week is None:
            return float("nan")
        return safe_uplift(nl_series["index"].get(week), nl_baseline)

    def net_of(exposed_up: float, control_up: float) -> float:
        return exposed_up - control_up if pd.notna(exposed_up) and pd.notna(control_up) else float("nan")

    # Net uplift, week by week: exposed uplift minus control uplift in the SAME
    # week. net_peak_uplift is the max of that net series (not the exposed
    # country's own peak week re-netted) -- the week where the gap vs. control is
    # largest need not be the same week the exposed country itself peaked.
    net_window = pd.Series(
        {
            wk: net_of(uplift_window[wk], control_uplift_at(wk, event, topic, series_map, baselines))
            for wk in window_weeks
        }
    )
    net_peak_uplift = net_window.max() if net_window.notna().any() else float("nan")
    net_persistence_12w = net_of(
        persistence_12w, control_uplift_at(persistence_week, event, topic, series_map, baselines)
    )

    net_window_vs_nl = pd.Series({wk: net_of(uplift_window[wk], nl_uplift_at(wk)) for wk in window_weeks})
    net_peak_vs_nl = net_window_vs_nl.max() if net_window_vs_nl.notna().any() else float("nan")
    net_persistence_vs_nl = net_of(persistence_12w, nl_uplift_at(persistence_week))

    return {
        "event_id": event.event_id,
        "event_name": event.event_name,
        "group": event.group,
        "country": country,
        "topic": topic,
        "exposed": country in event.exposed_countries,
        "baseline": baseline,
        "peak_uplift": peak_uplift,
        "half_life_weeks": half_life_weeks,
        "persistence_12w": persistence_12w,
        "net_peak_uplift": net_peak_uplift,
        "net_persistence_12w": net_persistence_12w,
        "net_peak_vs_nl": net_peak_vs_nl,
        "net_persistence_vs_nl": net_persistence_vs_nl,
    }


def build_table(weekly: pd.DataFrame) -> pd.DataFrame:
    series_by_topic = {topic: {c: series_for(weekly, c, topic) for c in COUNTRIES} for topic in TOPICS}
    nl_full_series = series_for(weekly, NL_COUNTRY, NL_TOPIC)

    rows = []
    for event in EVENTS:
        event_week = week_start_of(event.event_start)
        baselines_by_topic = {
            topic: {c: compute_baseline(series_by_topic[topic][c], event_week) for c in COUNTRIES}
            for topic in TOPICS
        }
        nl_baseline = compute_baseline(nl_full_series, event_week)
        for topic in TOPICS:
            for country in COUNTRIES:
                rows.append(
                    compute_row(
                        event,
                        country,
                        topic,
                        series_by_topic[topic],
                        baselines_by_topic[topic],
                        nl_full_series,
                        nl_baseline,
                    )
                )
    return pd.DataFrame(rows)


def plot_event_chart(weekly: pd.DataFrame, event: Event, out_path: Path) -> None:
    event_week = week_start_of(event.event_start)
    end_week = week_start_of(event.event_end)
    start_window = event_week - pd.Timedelta(weeks=CHART_WEEKS_BEFORE)
    end_window = event_week + pd.Timedelta(weeks=CHART_WEEKS_AFTER)
    weeks = pd.date_range(start_window, end_window, freq="7D")
    offsets = [(wk - event_week).days / 7 for wk in weeks]

    series_map = {c: series_for(weekly, c, "basketball") for c in COUNTRIES}
    baselines = {c: compute_baseline(series_map[c], event_week) for c in COUNTRIES}

    fig, ax = plt.subplots(figsize=(10, 6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    end_offset = (end_week - event_week).days / 7
    ax.axvspan(0, end_offset + 1, color="#c3c2b7", alpha=0.25, zorder=0)

    other_line = None
    color_i = 0
    for country in COUNTRIES:
        values = [series_map[country]["index"].get(wk) for wk in weeks]
        if country in event.exposed_countries:
            color = EXPOSED_COLORS[color_i % len(EXPOSED_COLORS)]
            color_i += 1
            ax.plot(offsets, values, linewidth=2.5, color=color, label=country, zorder=3)
        else:
            (line,) = ax.plot(offsets, values, linewidth=1, color="#c3c2b7", zorder=1)
            other_line = other_line or line

    if other_line is not None:
        other_line.set_label("Other markets")

    # Control: median uplift across unexposed markets, displayed as a synthetic
    # index (100 x (1 + uplift)) so it sits on the same baseline=100 scale as
    # every country's own index line.
    control_display = [
        100 * (1 + control_uplift_at(wk, event, "basketball", series_map, baselines))
        for wk in weeks
    ]
    ax.plot(
        offsets, control_display, linewidth=1.5, color="#0b0b0b", linestyle="--",
        label="Control (median, unexposed markets)", zorder=2,
    )

    date_label = (
        f"{event.event_start}" if event.event_start == event.event_end
        else f"{event.event_start} to {event.event_end}"
    )
    ax.set_yscale("log")
    ax.set_title(f"{event.event_name} -- {date_label}", color="#0b0b0b")
    ax.set_xlabel("Weeks relative to event start", color="#52514e")
    ax.set_ylabel("Basketball index (2019 weekly avg = 100, log scale)", color="#52514e")
    ax.grid(True, which="major", color="#e1e0d9", linewidth=0.8)
    ax.grid(True, which="minor", color="#e1e0d9", linewidth=0.4)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(colors="#898781")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def print_summary(table: pd.DataFrame) -> None:
    print("=== Basketball, exposed country only, by group ===")
    subset = table[(table["topic"] == "basketball") & (table["exposed"])]
    for group in ("nba_event", "national_team"):
        print(f"\n{group}:")
        rows = subset[subset["group"] == group]
        for _, row in rows.iterrows():
            hl = "NULL" if row["half_life_weeks"] is None or pd.isna(row["half_life_weeks"]) else f"{row['half_life_weeks']:.0f}w"
            print(
                f"  {row['event_name']:<18} ({row['country']:<8}) "
                f"peak={row['peak_uplift']*100:+6.1f}%  half_life={hl:>5}  "
                f"persist_12w={row['persistence_12w']*100:+6.1f}%  "
                f"net_peak={row['net_peak_uplift']*100:+6.1f}%  net_persist={row['net_persistence_12w']*100:+6.1f}%"
            )

    print("\n=== Flags ===")
    null_hl = subset[subset["half_life_weeks"].isna()]
    if len(null_hl):
        print("NULL half-life (didn't fall below peak/2 within 26 weeks):")
        for _, row in null_hl.iterrows():
            print(f"  {row['event_name']} ({row['country']})")
    else:
        print("No NULL half-lives among exposed/basketball rows.")

    implausible = subset[(subset["peak_uplift"] > 10) | (subset["peak_uplift"] < -0.9)]
    if len(implausible):
        print("Implausible peak_uplift (>1000% or near-total collapse):")
        for _, row in implausible.iterrows():
            print(f"  {row['event_name']} ({row['country']}): {row['peak_uplift']*100:+.1f}%")
    else:
        print("No implausible peak_uplift values flagged (threshold: >1000% or <-90%).")

    print(
        "\nT2 (fiba_wc_2023) tournament start date: VERIFIED via web search "
        "(Wikipedia/FIBA) as 2023-08-25 -- matches the fallback given in the brief."
    )


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    weekly = load_weekly()

    table = build_table(weekly)
    table.to_csv(TABLE_CSV, index=False)

    for event in EVENTS:
        plot_event_chart(weekly, event, CHARTS_DIR / f"event_{event.event_id}.png")

    print_summary(table)


if __name__ == "__main__":
    main()
