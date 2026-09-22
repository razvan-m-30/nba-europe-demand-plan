"""Collect Wikipedia pageview data used as an interest signal for the demand plan."""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import requests

USER_AGENT = "nba-europe-demand-plan/0.1 (github.com/razvan-m-30; student project)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_SLEEP_SECONDS = 0.5
PAGEVIEWS_START = "20190101"

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TITLES_CSV = RAW_DIR / "titles.csv"

# lang -> (country, {topic: input_title})
ARTICLES: dict[str, tuple[str, dict[str, str]]] = {
    "en": ("UK", {"basketball": "Basketball", "nba": "NBA"}),
    "fr": ("France", {"basketball": "Basket-ball", "nba": "National Basketball Association"}),
    "es": ("Spain", {"basketball": "Baloncesto", "nba": "NBA"}),
    "it": ("Italy", {"basketball": "Pallacanestro", "nba": "NBA"}),
    "de": ("Germany", {"basketball": "Basketball", "nba": "National Basketball Association"}),
    "tr": ("Turkey", {"basketball": "Basketbol", "nba": "NBA"}),
    "nl": ("Netherlands", {"basketball": "Basketbal", "nba": "NBA"}),
}


@dataclass
class TitleResolution:
    lang: str
    country: str
    topic: str
    input_title: str
    canonical_title: str | None
    redirected: bool
    missing: bool


def _retry_delay(resp: requests.Response) -> float:
    """Delay before retrying: the server's Retry-After if it sent one, else the default sleep."""
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
    """GET with one retry on request errors or 429/5xx, sleeping between attempts. Raises on final failure."""
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


def resolve_title(session: requests.Session, lang: str, input_title: str) -> dict:
    """Look up a title via the MediaWiki API, following redirects. Raises on failure."""
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {"action": "query", "titles": input_title, "redirects": 1, "format": "json"}
    resp = _request_with_retry(session, url, params=params)
    return resp.json()


def parse_title_resolution(
    lang: str, country: str, topic: str, input_title: str, data: dict
) -> TitleResolution:
    query = data.get("query", {})
    pages = query.get("pages", {})
    redirected = bool(query.get("redirects"))
    page = next(iter(pages.values()), None)
    if page is None or "missing" in page:
        return TitleResolution(lang, country, topic, input_title, None, redirected, True)
    return TitleResolution(lang, country, topic, input_title, page["title"], redirected, False)


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


def encode_title_for_path(title: str) -> str:
    return urllib.parse.quote(title.replace(" ", "_"), safe="")


def fetch_pageviews(session: requests.Session, lang: str, canonical_title: str, end_date: str) -> dict:
    """Fetch the raw daily pageviews payload for one article. Raises on failure."""
    encoded_title = encode_title_for_path(canonical_title)
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{lang}.wikipedia/all-access/user/{encoded_title}/daily/{PAGEVIEWS_START}/{end_date}"
    )
    resp = _request_with_retry(session, url)
    return resp.json()


def save_pageviews_json(lang: str, topic: str, payload: dict) -> Path:
    out_path = RAW_DIR / f"pageviews_{lang}_{topic}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def print_summary(
    resolutions: list[TitleResolution],
    lookup_errors: list[tuple[str, str, str, Exception]],
    pageview_files: dict[tuple[str, str], Path],
    pageview_errors: list[tuple[str, str, str, Exception]],
) -> None:
    print("\n=== Title resolution ===")
    redirected = [r for r in resolutions if r.redirected and not r.missing]
    missing = [r for r in resolutions if r.missing]

    print("Redirected:" if redirected else "Redirected: none")
    for r in redirected:
        print(f"  {r.lang}:{r.topic}  '{r.input_title}' -> '{r.canonical_title}'")

    print("Missing (skipped, not substituted):" if missing else "Missing: none")
    for r in missing:
        print(f"  {r.lang}:{r.topic}  '{r.input_title}'")

    if lookup_errors:
        print("Lookup failed (skipped, status unknown):")
        for lang, topic, input_title, exc in lookup_errors:
            print(f"  {lang}:{topic}  '{input_title}': {exc}")

    print("\n=== Pageviews files ===")
    if not pageview_files:
        print("No pageviews files were written.")
    for (lang, topic), path in pageview_files.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if items:
            timestamps = sorted(item["timestamp"] for item in items)
            date_range = f"{timestamps[0][:8]}-{timestamps[-1][:8]}"
        else:
            date_range = "n/a (no rows)"
        print(f"  {path.name}: {len(items)} rows, {date_range}")

    if pageview_errors:
        print("Pageviews fetch failed:")
        for lang, topic, canonical_title, exc in pageview_errors:
            print(f"  {lang}:{topic}  '{canonical_title}': {exc}")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    resolutions: list[TitleResolution] = []
    lookup_errors: list[tuple[str, str, str, Exception]] = []
    for lang, (country, topics) in ARTICLES.items():
        for topic, input_title in topics.items():
            try:
                data = resolve_title(session, lang, input_title)
            except (requests.RequestException, ValueError) as exc:
                print(f"[ERROR] title lookup failed for {lang}:{topic} '{input_title}': {exc}", file=sys.stderr)
                lookup_errors.append((lang, topic, input_title, exc))
                continue
            resolutions.append(parse_title_resolution(lang, country, topic, input_title, data))

    write_titles_csv(resolutions)

    end_date = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    pageview_files: dict[tuple[str, str], Path] = {}
    pageview_errors: list[tuple[str, str, str, Exception]] = []
    for r in resolutions:
        if r.missing or r.canonical_title is None:
            continue
        try:
            payload = fetch_pageviews(session, r.lang, r.canonical_title, end_date)
        except (requests.RequestException, ValueError) as exc:
            print(f"[ERROR] pageviews fetch failed for {r.lang}:{r.topic} '{r.canonical_title}': {exc}", file=sys.stderr)
            pageview_errors.append((r.lang, r.topic, r.canonical_title, exc))
            continue
        pageview_files[(r.lang, r.topic)] = save_pageviews_json(r.lang, r.topic, payload)

    print_summary(resolutions, lookup_errors, pageview_files, pageview_errors)


if __name__ == "__main__":
    main()
