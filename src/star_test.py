"""Star vs league test: around NBA Paris 2025 / NBA Berlin 2026, did attention go
to the local star player or to the event itself?"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
WEEKLY_PARQUET = ROOT / "data" / "processed" / "weekly_interest.parquet"
TITLES_CSV = RAW_DIR / "titles_players.csv"
STAR_TEST_CSV = ROOT / "outputs" / "star_test.csv"

USER_AGENT = "nba-europe-demand-plan/0.1 (github.com/razvan-m-30; student project)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_SLEEP_SECONDS = 0.5
PAGEVIEWS_START = "20241001"
PAGEVIEWS_END = "20260430"

BASELINE_WEEKS = 8
PEAK_WINDOW_EXTRA_WEEKS = 4
GAP_CLUSTER_THRESHOLD = 3  # same rule as process_interest.py: 3+ day runs left NULL

STAR_RATIO = 3.0
EVENT_RATIO = 1.5
SEARCH_HINT = "Basketball"  # same spelling in German; close enough in French full-text search


@dataclass
class PlayerSpec:
    lang: str
    country: str
    slug: str  # used as "topic" in titles_players.csv and in pageviews filenames
    input_title: str


@dataclass
class EventSpec:
    event_id: str
    event_name: str
    lang: str
    event_start: date
    event_end: date
    players: list[PlayerSpec]


PLAYERS = [
    PlayerSpec("de", "Germany", "franz_wagner", "Franz Wagner"),
    PlayerSpec("de", "Germany", "moritz_wagner", "Moritz Wagner"),
    PlayerSpec("fr", "France", "wembanyama", "Victor Wembanyama"),
]

EVENTS = [
    EventSpec(
        "N2", "nba_paris_2025", "fr", date(2025, 1, 23), date(2025, 1, 25),
        [p for p in PLAYERS if p.slug == "wembanyama"],
    ),
    EventSpec(
        "N3", "nba_berlin_2026", "de", date(2026, 1, 15), date(2026, 1, 15),
        [p for p in PLAYERS if p.lang == "de"],
    ),
]


# ---------------------------------------------------------------------------
# HTTP (same method as collect_wikipedia.py: MediaWiki + Wikimedia REST, with
# one retry on 429/5xx honoring Retry-After)
# ---------------------------------------------------------------------------


def _retry_delay(resp: requests.Response) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(float(retry_after), REQUEST_SLEEP_SECONDS)
        except ValueError:
            pass
    return REQUEST_SLEEP_SECONDS


def _request_with_retry(
    session: requests.Session, url: str, *, params: dict | None = None
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(REQUEST_SLEEP_SECONDS)
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            last_exc = requests.HTTPError(f"{resp.status_code} {resp.reason} for {url}")
            time.sleep(_retry_delay(resp))
            continue
        resp.raise_for_status()
        time.sleep(REQUEST_SLEEP_SECONDS)
        return resp
    assert last_exc is not None
    raise last_exc


def encode_title_for_path(title: str) -> str:
    return urllib.parse.quote(title.replace(" ", "_"), safe="")


def fetch_pageviews(session: requests.Session, lang: str, canonical_title: str) -> dict:
    encoded_title = encode_title_for_path(canonical_title)
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{lang}.wikipedia/all-access/user/{encoded_title}/daily/{PAGEVIEWS_START}/{PAGEVIEWS_END}"
    )
    resp = _request_with_retry(session, url)
    return resp.json()


def save_pageviews_json(lang: str, slug: str, payload: dict) -> Path:
    out_path = RAW_DIR / f"pageviews_{lang}_{slug}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Title resolution, with a disambiguation-page / search fallback -- both
# "Franz Wagner" and "Moritz Wagner" land on disambiguation pages on
# de.wikipedia, not the player's own article.
# ---------------------------------------------------------------------------


@dataclass
class TitleResolution:
    lang: str
    country: str
    topic: str
    input_title: str
    canonical_title: str | None
    redirected: bool
    missing: bool


def mediawiki_lookup(session: requests.Session, lang: str, title: str) -> dict:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query", "titles": title, "redirects": 1, "format": "json",
        "prop": "pageprops|extracts", "exintro": 1, "explaintext": 1,
    }
    resp = _request_with_retry(session, url, params=params)
    return resp.json()


def mediawiki_search(session: requests.Session, lang: str, query: str) -> list[str]:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 5}
    resp = _request_with_retry(session, url, params=params)
    return [r["title"] for r in resp.json().get("query", {}).get("search", [])]


def first_page(data: dict) -> dict | None:
    return next(iter(data.get("query", {}).get("pages", {}).values()), None)


def is_usable(page: dict | None) -> bool:
    return page is not None and "missing" not in page and "disambiguation" not in page.get("pageprops", {})


def find_disambiguation_candidate(extract: str, hint: str) -> str | None:
    """Pick the qualified title from a disambiguation page's entry mentioning `hint`."""
    for line in extract.splitlines():
        if hint.lower() in line.lower():
            m = re.match(r"^(.*?\([^)]*\))", line.strip())
            if m:
                return m.group(1).strip()
    return None


def resolve_player_title(session: requests.Session, player: PlayerSpec) -> tuple[TitleResolution, str]:
    """Returns (resolution, method). method is one of: direct, redirect,
    disambiguation (resolved via the disambiguation page's own listing), search
    (resolved via full-text search), not-found."""
    data = mediawiki_lookup(session, player.lang, player.input_title)
    query = data.get("query", {})
    redirected = bool(query.get("redirects"))
    page = first_page(data)

    if is_usable(page):
        return (
            TitleResolution(player.lang, player.country, player.slug, player.input_title, page["title"], redirected, False),
            "redirect" if redirected else "direct",
        )

    if page is not None and "disambiguation" in page.get("pageprops", {}):
        candidate = find_disambiguation_candidate(page.get("extract", ""), SEARCH_HINT)
        if candidate:
            verify = mediawiki_lookup(session, player.lang, candidate)
            vpage = first_page(verify)
            if is_usable(vpage):
                return (
                    TitleResolution(player.lang, player.country, player.slug, player.input_title, vpage["title"], False, False),
                    "disambiguation",
                )

    for candidate in mediawiki_search(session, player.lang, f"{player.input_title} {SEARCH_HINT}"):
        verify = mediawiki_lookup(session, player.lang, candidate)
        vpage = first_page(verify)
        if is_usable(vpage):
            return (
                TitleResolution(player.lang, player.country, player.slug, player.input_title, vpage["title"], False, False),
                "search",
            )

    return (
        TitleResolution(player.lang, player.country, player.slug, player.input_title, None, False, True),
        "not-found",
    )


def write_titles_csv(resolutions: list[TitleResolution]) -> None:
    with TITLES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["lang", "country", "topic", "input_title", "canonical_title", "redirected", "missing"]
        )
        for r in resolutions:
            writer.writerow(
                [r.lang, r.country, r.topic, r.input_title, r.canonical_title or "", r.redirected, r.missing]
            )


# ---------------------------------------------------------------------------
# Daily -> weekly (same gap rule as process_interest.py, no winsorization --
# not re-requested for this narrower test)
# ---------------------------------------------------------------------------


@dataclass
class GapRun:
    start: date
    end: date
    days: int


def find_gap_runs(missing_days: list[date]) -> list[GapRun]:
    days = sorted(missing_days)
    runs: list[GapRun] = []
    for day in days:
        if runs and (day - runs[-1].end).days == 1:
            runs[-1] = GapRun(runs[-1].start, day, runs[-1].days + 1)
        else:
            runs.append(GapRun(day, day, 1))
    return runs


def build_weekly_views(payload: dict) -> pd.DataFrame:
    """Full daily calendar, isolated (<3 day) gaps zero-filled, 3+ day gaps left
    NULL, summed to complete ISO (Monday-start) weeks."""
    items = payload.get("items", [])
    if not items:
        return pd.DataFrame(columns=["week_start", "views"])

    daily = pd.DataFrame(
        {
            "day": pd.to_datetime([i["timestamp"][:8] for i in items], format="%Y%m%d"),
            "views": [i["views"] for i in items],
        }
    ).sort_values("day")

    calendar = pd.DataFrame({"day": pd.date_range(daily["day"].min(), daily["day"].max(), freq="D")})
    merged = calendar.merge(daily, on="day", how="left")
    missing_days = merged.loc[merged["views"].isna(), "day"].dt.date.tolist()
    for run in find_gap_runs(missing_days):
        if run.days < GAP_CLUSTER_THRESHOLD:
            mask = (merged["day"].dt.date >= run.start) & (merged["day"].dt.date <= run.end)
            merged.loc[mask, "views"] = 0

    merged["week_start"] = merged["day"] - pd.to_timedelta(merged["day"].dt.weekday, unit="D")
    weekly = merged.groupby("week_start").agg(views=("views", "sum"), n_days=("day", "count")).reset_index()
    return weekly[weekly["n_days"] == 7][["week_start", "views"]]


def load_topic_weekly(weekly_df: pd.DataFrame, lang: str, topic: str) -> pd.DataFrame:
    sub = weekly_df[(weekly_df["lang"] == lang) & (weekly_df["topic"] == topic)]
    return sub[["week_start", "views"]].sort_values("week_start").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def week_start_of(d: date) -> pd.Timestamp:
    ts = pd.Timestamp(d)
    return ts - pd.Timedelta(days=ts.weekday())


def compute_metrics(weekly_views: pd.DataFrame, event_week: pd.Timestamp) -> dict:
    series = weekly_views.set_index("week_start")["views"]

    baseline_weeks = [event_week - pd.Timedelta(weeks=i) for i in range(1, BASELINE_WEEKS + 1)]
    baseline_vals = series.reindex(baseline_weeks).dropna()
    baseline = float(baseline_vals.median()) if len(baseline_vals) else float("nan")

    window_weeks = pd.date_range(event_week, event_week + pd.Timedelta(weeks=PEAK_WINDOW_EXTRA_WEEKS), freq="7D")
    window_vals = series.reindex(window_weeks)

    if pd.notna(baseline) and baseline > 0:
        uplift = window_vals / baseline - 1
        peak_uplift = float(uplift.max()) if uplift.notna().any() else float("nan")
        extra_views = float((window_vals - baseline).clip(lower=0).fillna(0).sum())
    else:
        peak_uplift, extra_views = float("nan"), float("nan")

    return {"baseline_views": baseline, "peak_uplift": peak_uplift, "extra_views": extra_views}


def classify(player_peak_uplift: float, league_peak_uplift: float) -> str:
    if pd.isna(player_peak_uplift) or pd.isna(league_peak_uplift):
        return "UNVERIFIED (missing data)"
    if league_peak_uplift <= 0:
        return "attention went mainly to the star" if player_peak_uplift > 0 else "UNVERIFIED (no league lift to compare against)"
    ratio = player_peak_uplift / league_peak_uplift
    if ratio >= STAR_RATIO:
        return "attention went mainly to the star"
    if ratio <= EVENT_RATIO:
        return "attention was on the event"
    return "mixed"


# ---------------------------------------------------------------------------
# Placebo weeks: 3 ordinary regular-season weeks per player, same season as
# their event, >=4 weeks from the event week, clear of NBA All-Star weekend
# (2025: Feb 14-16 SF; 2026: Feb 13-15 Inglewood -- both verified via web
# search) and the February trade deadline. All chosen with >=8 weeks of
# pageview history behind them (data starts 2024-10-01).
# ---------------------------------------------------------------------------

PLACEBO_WEEKS: dict[str, list[date]] = {
    # N2 event week is 2025-01-20; season 2024-25. Pre-event safe window is
    # only Dec 1-22 (narrow, and still close to the trade-deadline/All-Star
    # run-up), so all 3 are picked well after the Feb 17 buffer instead.
    "wembanyama": [date(2025, 3, 3), date(2025, 3, 17), date(2025, 3, 31)],
    # N3 event week is 2026-01-12; season 2025-26. Picked from well before
    # the Dec 15 buffer (early/mid season) and once after the Feb 9 buffer.
    "franz_wagner": [date(2025, 10, 20), date(2025, 11, 17), date(2026, 3, 2)],
    "moritz_wagner": [date(2025, 10, 20), date(2025, 11, 17), date(2026, 3, 2)],
}


def placebo_peak_uplift(weekly_views: pd.DataFrame, placebo_dates: list[date]) -> tuple[float, list[dict]]:
    """Median peak_uplift across the placebo weeks, plus per-week detail."""
    details = []
    for d in placebo_dates:
        week = week_start_of(d)
        metrics = compute_metrics(weekly_views, week)
        details.append({"week": week.date(), **metrics})
    uplifts = [row["peak_uplift"] for row in details if pd.notna(row["peak_uplift"])]
    median_uplift = float(pd.Series(uplifts).median()) if uplifts else float("nan")
    return median_uplift, details


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    resolutions: dict[str, TitleResolution] = {}
    methods: dict[str, str] = {}
    for player in PLAYERS:
        res, method = resolve_player_title(session, player)
        resolutions[player.slug] = res
        methods[player.slug] = method
        if res.missing:
            print(f"[ERROR] could not resolve a title for {player.lang}:{player.input_title}", file=sys.stderr)

    write_titles_csv(list(resolutions.values()))

    pageview_payloads: dict[str, dict] = {}
    for player in PLAYERS:
        res = resolutions[player.slug]
        if res.missing or res.canonical_title is None:
            continue
        try:
            payload = fetch_pageviews(session, player.lang, res.canonical_title)
        except (requests.RequestException, ValueError) as exc:
            print(f"[ERROR] pageviews fetch failed for {player.lang}:{res.canonical_title}: {exc}", file=sys.stderr)
            continue
        save_pageviews_json(player.lang, player.slug, payload)
        pageview_payloads[player.slug] = payload

    player_weekly = {slug: build_weekly_views(payload) for slug, payload in pageview_payloads.items()}
    weekly_df = pd.read_parquet(WEEKLY_PARQUET)

    rows = []
    placebo_detail_by_player: dict[str, list[dict]] = {}
    for event in EVENTS:
        event_week = week_start_of(event.event_start)

        topic_metrics = {}
        for topic in ("basketball", "nba"):
            topic_weekly = load_topic_weekly(weekly_df, event.lang, topic)
            topic_metrics[topic] = compute_metrics(topic_weekly, event_week)
            rows.append(
                {
                    "event": event.event_name,
                    "article": topic,
                    "lang": event.lang,
                    **topic_metrics[topic],
                    "placebo_peak_uplift": float("nan"),
                    "event_vs_placebo": float("nan"),
                    "verdict": "",
                }
            )

        league_peak_uplift = max(
            v for v in (topic_metrics["basketball"]["peak_uplift"], topic_metrics["nba"]["peak_uplift"]) if pd.notna(v)
        ) if any(pd.notna(topic_metrics[t]["peak_uplift"]) for t in ("basketball", "nba")) else float("nan")

        for player in event.players:
            weekly = player_weekly.get(player.slug)
            if weekly is None:
                rows.append(
                    {
                        "event": event.event_name, "article": player.input_title, "lang": player.lang,
                        "baseline_views": float("nan"), "peak_uplift": float("nan"), "extra_views": float("nan"),
                        "placebo_peak_uplift": float("nan"), "event_vs_placebo": float("nan"),
                        "verdict": "UNVERIFIED (no pageviews data)",
                    }
                )
                continue
            metrics = compute_metrics(weekly, event_week)
            placebo_median, placebo_detail = placebo_peak_uplift(weekly, PLACEBO_WEEKS[player.slug])
            placebo_detail_by_player[player.slug] = placebo_detail
            event_vs_placebo = (
                metrics["peak_uplift"] / placebo_median
                if pd.notna(metrics["peak_uplift"]) and pd.notna(placebo_median) and placebo_median > 0
                else float("nan")
            )
            verdict = classify(metrics["peak_uplift"], league_peak_uplift)
            rows.append(
                {
                    "event": event.event_name, "article": player.input_title, "lang": player.lang,
                    **metrics, "placebo_peak_uplift": placebo_median, "event_vs_placebo": event_vs_placebo,
                    "verdict": verdict,
                }
            )

    table = pd.DataFrame(
        rows,
        columns=[
            "event", "article", "lang", "baseline_views", "peak_uplift", "extra_views",
            "placebo_peak_uplift", "event_vs_placebo", "verdict",
        ],
    )
    table.to_csv(STAR_TEST_CSV, index=False)

    print("=== Title resolution ===")
    for player in PLAYERS:
        res, method = resolutions[player.slug], methods[player.slug]
        status = "MISSING" if res.missing else res.canonical_title
        print(f"  {player.lang}:{player.input_title} -> {status}  [{method}]")

    print("\n=== Placebo weeks chosen ===")
    for player in PLAYERS:
        if player.slug not in placebo_detail_by_player:
            continue
        print(f"  {player.input_title} ({', '.join(d.isoformat() for d in PLACEBO_WEEKS[player.slug])}):")
        for row in placebo_detail_by_player[player.slug]:
            print(f"    week of {row['week']}: baseline={row['baseline_views']:.1f}  peak_uplift={row['peak_uplift']*100:+.1f}%")

    print("\n=== star_test.csv ===")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
