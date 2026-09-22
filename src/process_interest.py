"""Process raw Wikipedia pageviews into an indexed weekly interest series."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CHARTS_DIR = ROOT / "outputs" / "charts"
WEEKLY_PARQUET = PROCESSED_DIR / "weekly_interest.parquet"

# A run of at least this many consecutive missing days is flagged as a
# possible collection outage rather than ordinary zero-view days.
GAP_CLUSTER_THRESHOLD = 3
GAP_REPORT_SERIES = [("it", "nba"), ("nl", "nba")]

# Winsorize: cap a day above WINSORIZE_MULTIPLIER x its trailing median at that cap.
WINSORIZE_MULTIPLIER = 5
TRAILING_MEDIAN_WEEKS = 8
CAPPED_DAYS_CSV = ROOT / "outputs" / "capped_days.csv"

# Fixed categorical color order (validated palette, dataviz skill default),
# assigned by language so each country keeps the same color across charts.
COUNTRY_COLORS = {
    "UK": "#2a78d6",
    "France": "#eb6834",
    "Spain": "#1baf7a",
    "Italy": "#eda100",
    "Germany": "#e87ba4",
    "Turkey": "#008300",
    "Netherlands": "#4a3aa7",
}

EVENTS = [
    (date(2023, 6, 22), "Wembanyama draft"),
    (date(2024, 7, 27), "Paris 2024 Olympics"),
    (date(2025, 1, 23), "Paris games (2025)"),
    (date(2026, 1, 15), "Berlin game (2026)"),
]


def load_joined(con: duckdb.DuckDBPyConnection) -> None:
    """Register a `joined` view: one row per (lang, country, topic, day, views)."""
    pageviews_glob = (RAW_DIR / "pageviews_*.json").as_posix()
    titles_csv = (RAW_DIR / "titles.csv").as_posix()
    con.execute(f"""
        CREATE OR REPLACE VIEW joined AS
        WITH raw AS (
            SELECT
                split_part(item.project, '.', 1) AS lang,
                item.article AS wiki_title,
                strptime(item.timestamp, '%Y%m%d%H')::DATE AS day,
                item.views AS views
            FROM read_json_auto('{pageviews_glob}') AS t,
                 UNNEST(t.items) AS u(item)
        ),
        titles AS (
            SELECT lang, country, topic, replace(canonical_title, ' ', '_') AS wiki_title
            FROM read_csv_auto('{titles_csv}')
            WHERE NOT missing
        )
        SELECT r.lang, ti.country, ti.topic, r.day, r.views
        FROM raw r
        JOIN titles ti USING (lang, wiki_title)
    """)


def build_daily(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Full daily calendar per series (own min/max date). Missing days are NULL
    views here; apply_gap_fill decides which ones become 0."""
    return con.execute("""
        WITH series_range AS (
            SELECT lang, country, topic, MIN(day) AS start_day, MAX(day) AS end_day
            FROM joined
            GROUP BY lang, country, topic
        ),
        calendar AS (
            SELECT lang, country, topic,
                   UNNEST(generate_series(start_day, end_day, INTERVAL 1 DAY))::DATE AS day
            FROM series_range
        )
        SELECT c.lang, c.country, c.topic, c.day,
               j.views AS views,
               (j.day IS NULL) AS was_filled
        FROM calendar c
        LEFT JOIN joined j USING (lang, country, topic, day)
        ORDER BY lang, topic, day
    """).fetchdf()


@dataclass
class GapRun:
    start: date
    end: date
    days: int


def find_gap_runs(missing_days: pd.Series) -> list[GapRun]:
    """Group a sorted series of missing dates into consecutive-day runs."""
    days = sorted(missing_days)
    runs: list[GapRun] = []
    for day in days:
        if runs and (day - runs[-1].end).days == 1:
            runs[-1] = GapRun(runs[-1].start, day, runs[-1].days + 1)
        else:
            runs.append(GapRun(day, day, 1))
    return runs


def apply_gap_fill(daily: pd.DataFrame) -> pd.DataFrame:
    """Zero-fill isolated gaps (run length < GAP_CLUSTER_THRESHOLD). Longer runs
    (3+ days, e.g. it/nba's July 2026 outage) are left NULL so they're excluded
    from weekly sums rather than faked as zero interest."""
    daily = daily.copy()
    for (lang, country, topic), group in daily.groupby(["lang", "country", "topic"], sort=False):
        missing_days = pd.to_datetime(group.loc[group["was_filled"], "day"]).dt.date
        for run in find_gap_runs(missing_days):
            if run.days < GAP_CLUSTER_THRESHOLD:
                day_col = pd.to_datetime(group["day"]).dt.date
                in_run = group.index[(day_col >= run.start) & (day_col <= run.end)]
                daily.loc[in_run, "views"] = 0
    return daily


def winsorize_daily(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cap any day above WINSORIZE_MULTIPLIER x its trailing median (the preceding
    TRAILING_MEDIAN_WEEKS*7 days, per series) at that cap. A day with no trailing
    history yet, or a trailing median of 0, is left uncapped -- there's no baseline
    to judge it against. Returns (daily_with_caps_applied, capped_days_log)."""
    daily = daily.sort_values(["lang", "country", "topic", "day"]).reset_index(drop=True)
    daily["views"] = daily["views"].astype("float64")
    window_days = TRAILING_MEDIAN_WEEKS * 7
    trailing_median = (
        daily.groupby(["lang", "country", "topic"])["views"]
        .apply(lambda s: s.rolling(window_days, min_periods=1).median().shift(1))
        .reset_index(level=[0, 1, 2], drop=True)
    )
    cap = trailing_median * WINSORIZE_MULTIPLIER
    exceeds = (daily["views"] > cap) & (cap > 0)

    capped_log = pd.DataFrame(
        {
            "series": daily.loc[exceeds, "lang"] + "/" + daily.loc[exceeds, "topic"],
            "date": daily.loc[exceeds, "day"],
            "raw": daily.loc[exceeds, "views"],
            "capped": cap[exceeds],
        }
    ).reset_index(drop=True)

    daily = daily.copy()
    daily.loc[exceeds, "views"] = cap[exceeds]
    return daily, capped_log


def report_gaps(daily: pd.DataFrame) -> list[str]:
    """Build the missing-date report lines for the flagged series."""
    lines = []
    for lang, topic in GAP_REPORT_SERIES:
        series = daily[(daily["lang"] == lang) & (daily["topic"] == topic)]
        missing = pd.to_datetime(series.loc[series["was_filled"], "day"]).dt.date
        runs = find_gap_runs(missing)
        country = series["country"].iloc[0] if len(series) else lang
        if not runs:
            lines.append(f"{lang}/{topic} ({country}): no missing days.")
            continue
        max_run = max(r.days for r in runs)
        verdict = (
            "clustered -- possible outage"
            if max_run >= GAP_CLUSTER_THRESHOLD
            else "scattered -- consistent with zero-view days the API omits"
        )
        run_strs = [
            f"{r.start}" if r.days == 1 else f"{r.start}..{r.end} ({r.days}d)" for r in runs
        ]
        lines.append(
            f"{lang}/{topic} ({country}): {len(missing)} missing day(s) across "
            f"{len(runs)} run(s), longest {max_run}d -> {verdict}"
        )
        lines.append(f"  dates: {', '.join(run_strs)}")
    return lines


def build_weekly_indexed(con: duckdb.DuckDBPyConnection, daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to complete ISO (Monday-start) weeks and index each series to its 2019 average."""
    con.register("daily", daily)
    weekly = con.execute("""
        WITH weekly_raw AS (
            SELECT lang, country, topic,
                   date_trunc('week', day)::DATE AS week_start,
                   date_part('isoyear', day)::BIGINT AS iso_year,
                   date_part('week', day)::BIGINT AS iso_week,
                   SUM(views) AS views,
                   COUNT(views) AS n_days
            FROM daily
            GROUP BY lang, country, topic, week_start, iso_year, iso_week
            HAVING COUNT(*) = 7
        ),
        baseline AS (
            SELECT lang, country, topic, AVG(views) AS baseline_views
            FROM weekly_raw
            WHERE iso_year = 2019
            GROUP BY lang, country, topic
        )
        SELECT w.week_start, w.iso_year, w.iso_week, w.lang, w.country, w.topic, w.views,
               w.views / b.baseline_views * 100 AS "index",
               (w.n_days < 7) AS incomplete,
               (w.lang = 'nl' AND w.topic = 'basketball') AS use_as_control
        FROM weekly_raw w
        JOIN baseline b USING (lang, country, topic)
        ORDER BY w.lang, w.topic, w.week_start
    """).fetchdf()
    con.unregister("daily")
    return weekly


def plot_sanity_chart(weekly: pd.DataFrame, topic: str, out_path: Path) -> None:
    subset = weekly[weekly["topic"] == topic]
    fig, ax = plt.subplots(figsize=(11, 6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    for country, color in COUNTRY_COLORS.items():
        series = subset[subset["country"] == country].sort_values("week_start")
        if series.empty:
            continue
        ax.plot(series["week_start"], series["index"], linewidth=2, color=color, label=country)

    for event_date, label in EVENTS:
        ax.axvline(event_date, color="#898781", linestyle="--", linewidth=1)
        ax.annotate(
            label,
            xy=(event_date, 1),
            xycoords=("data", "axes fraction"),
            xytext=(3, -3),
            textcoords="offset points",
            rotation=90,
            va="top",
            ha="left",
            fontsize=8,
            color="#52514e",
        )

    ax.set_yscale("log")
    ax.set_title(f"Wikipedia interest sanity check -- {topic}", color="#0b0b0b")
    ax.set_ylabel("Index (2019 weekly average = 100, log scale)", color="#52514e")
    ax.grid(True, which="major", color="#e1e0d9", linewidth=0.8)
    ax.grid(True, which="minor", color="#e1e0d9", linewidth=0.4)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c3c2b7")
    ax.tick_params(colors="#898781")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def turkey_diagnostic(weekly: pd.DataFrame) -> list[str]:
    """2019 baseline stability check for tr (both topics), with nl as a small-market
    comparison, plus tr's raw weekly views at the two index peak weeks. Diagnostic
    only -- doesn't change any data."""
    lines = []
    for lang, label in (("tr", "Turkey"), ("nl", "Netherlands")):
        for topic in ("basketball", "nba"):
            views_2019 = weekly.loc[
                (weekly["lang"] == lang) & (weekly["topic"] == topic) & (weekly["iso_year"] == 2019),
                "views",
            ].dropna()
            lowest = [f"{v:.0f}" for v in views_2019.sort_values().head(5)]
            lines.append(
                f"{label}/{topic} 2019 weekly views: total={views_2019.sum():.0f}  "
                f"mean={views_2019.mean():.1f}  median={views_2019.median():.1f}"
            )
            lines.append(f"  5 lowest weeks: {', '.join(lowest)}")
            if lang == "tr":
                stable = views_2019.median() >= 100
                verdict = (
                    "median >= ~100 -> baseline can support a reasonably stable index"
                    if stable
                    else "median < ~100 -> baseline is too thin, index for this series is unreliable"
                )
                lines.append(f"  stability check: {verdict}")

    lines.append("")
    lines.append("Turkey raw weekly views at the current index peak week per topic:")
    for topic in ("basketball", "nba"):
        tr_topic = weekly[(weekly["lang"] == "tr") & (weekly["topic"] == topic)]
        if tr_topic.empty:
            continue
        peak = tr_topic.loc[tr_topic["index"].idxmax()]
        lines.append(
            f"  tr/{topic} week of {peak['week_start'].date()}: "
            f"views={peak['views']:.0f}  index={peak['index']:.1f}"
        )
    return lines


def print_summary(daily: pd.DataFrame, weekly: pd.DataFrame, gap_lines: list[str]) -> None:
    print("=== Daily table ===")
    print(f"Rows: {len(daily)}")
    print(f"Date range: {daily['day'].min()} -> {daily['day'].max()}")

    print("\n=== Missing-day gap report ===")
    for line in gap_lines:
        print(line)

    print("\n=== Weekly table ===")
    print(f"Rows: {len(weekly)}")
    print(f"Week range: {weekly['week_start'].min()} -> {weekly['week_start'].max()}")
    n_incomplete = int(weekly["incomplete"].sum())
    print(f"Incomplete rows (built from < 7 non-null days): {n_incomplete}")
    if n_incomplete:
        for _, row in weekly[weekly["incomplete"]].iterrows():
            print(
                f"  {row['lang']}/{row['topic']} week of {row['week_start'].date()}: "
                f"views={row['views']}"
            )

    print("\n=== Highest-index week per country ===")
    for topic in ("basketball", "nba"):
        print(f"\n{topic}:")
        subset = weekly[weekly["topic"] == topic]
        top = subset.loc[subset.groupby("country")["index"].idxmax()].sort_values(
            "country"
        )
        for _, row in top.iterrows():
            print(
                f"  {row['country']:<12} week of {row['week_start'].date()}  "
                f"index={row['index']:.1f}"
            )


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    load_joined(con)

    daily = build_daily(con)
    gap_lines = report_gaps(daily)
    daily = apply_gap_fill(daily)
    daily, capped_log = winsorize_daily(daily)
    capped_log.to_csv(CAPPED_DAYS_CSV, index=False)

    weekly = build_weekly_indexed(con, daily)
    weekly.to_parquet(WEEKLY_PARQUET, index=False)

    plot_sanity_chart(weekly, "basketball", CHARTS_DIR / "sanity_basketball.png")
    plot_sanity_chart(weekly, "nba", CHARTS_DIR / "sanity_nba.png")

    print_summary(daily, weekly, gap_lines)
    print("\n=== Winsorized days (capped at 5x trailing 8-week median) ===")
    print(f"Total capped: {len(capped_log)}")
    if len(capped_log):
        for series, count in capped_log["series"].value_counts().sort_index().items():
            print(f"  {series}: {count}")
    print("\n=== Turkey diagnostic ===")
    for line in turkey_diagnostic(weekly):
        print(line)


if __name__ == "__main__":
    main()
