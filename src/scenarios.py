"""Step 4: translate the three NBA-game net uplifts into low/base/high demand
scenarios per host market."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parent.parent
ANALOGS_CSV = ROOT / "outputs" / "analogs_table.csv"
SCENARIOS_CSV = ROOT / "outputs" / "scenarios.csv"
PLAN_XLSX = ROOT / "outputs" / "plan.xlsx"

# scenario -> (source event_id, expected net_peak_uplift -- checked, not invented)
SCENARIO_SOURCE = {"low": "N2", "base": "N3", "high": "N4"}
EXPECTED_NET_PEAK = {"N2": -0.112, "N3": 0.261, "N4": 0.306}
TOLERANCE = 0.005  # 0.5 percentage points

K_VALUES = [0.25, 0.5]
PROBABILITIES = {"low": 0.25, "base": 0.50, "high": 0.25}  # judgement call, not derived from data

COUNTRIES = ["UK", "France", "Spain", "Italy", "Germany", "Turkey"]
OWN_EVENT_COUNTRIES = {"France", "Germany", "UK"}


def load_interest_uplifts() -> tuple[dict, list[tuple]]:
    """Reads net_peak_uplift (basketball, exposed) for N2/N3/N4 from
    analogs_table.csv, checks it against the expected values, and floors any
    negative value at 0%. Returns (scenario -> info dict, floor log)."""
    if not ANALOGS_CSV.exists():
        sys.exit(f"STOP: {ANALOGS_CSV} not found -- run src/analogs.py first.")
    df = pd.read_csv(ANALOGS_CSV)
    df = df[(df["topic"] == "basketball") & (df["exposed"])]

    result = {}
    floor_log = []
    for scenario, event_id in SCENARIO_SOURCE.items():
        row = df[df["event_id"] == event_id]
        if row.empty:
            sys.exit(f"STOP: no basketball/exposed row for event {event_id} in {ANALOGS_CSV}")
        raw = float(row["net_peak_uplift"].iloc[0])
        event_name = str(row["event_name"].iloc[0])
        country = str(row["country"].iloc[0])

        expected = EXPECTED_NET_PEAK[event_id]
        if abs(raw - expected) > TOLERANCE:
            sys.exit(
                f"STOP: {event_id} ({event_name}, {country}) net_peak_uplift={raw * 100:.2f}% "
                f"differs from the expected {expected * 100:.1f}% by more than "
                f"{TOLERANCE * 100:.1f} points -- re-check inputs before trusting these scenarios."
            )

        floored = raw < 0
        interest_uplift = max(raw, 0.0)
        if floored:
            floor_log.append((scenario, event_id, event_name, country, raw))

        result[scenario] = {
            "event_id": event_id,
            "event_name": event_name,
            "country": country,
            "raw_net_peak_uplift": raw,
            "interest_uplift": interest_uplift,
            "floored": floored,
        }
    return result, floor_log


def build_scenarios_table(interest: dict) -> pd.DataFrame:
    rows = []
    for country in COUNTRIES:
        own_event = country in OWN_EVENT_COUNTRIES
        for scenario, info in interest.items():
            for k in K_VALUES:
                rows.append(
                    {
                        "country": country,
                        "own_event": own_event,
                        "scenario": scenario,
                        "source_event": info["event_name"],
                        "interest_uplift": info["interest_uplift"],
                        "k": k,
                        "demand_uplift": info["interest_uplift"] * k,
                        "probability": PROBABILITIES[scenario],
                    }
                )
    return pd.DataFrame(
        rows,
        columns=[
            "country", "own_event", "scenario", "source_event",
            "interest_uplift", "k", "demand_uplift", "probability",
        ],
    )


def expected_demand_uplift(interest: dict, k: float) -> float:
    return sum(interest[s]["interest_uplift"] * k * PROBABILITIES[s] for s in ("low", "base", "high"))


# ---------------------------------------------------------------------------
# Excel output
# ---------------------------------------------------------------------------

PCT_FORMAT = "0.0%"
HEADER_FONT = Font(bold=True)


def write_scenarios_sheet(ws, interest: dict) -> None:
    ws.title = "Scenarios"
    ws.append(["Demand uplift by country and scenario (basketball category, vs. baseline plan)"])
    ws["A1"].font = Font(bold=True, size=12)
    row = 3
    for k in K_VALUES:
        ws.cell(row=row, column=1, value=f"k = {k}").font = HEADER_FONT
        row += 1
        headers = ["Country", "Own event", "Low", "Base", "High", "Expected"]
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = HEADER_FONT
        row += 1
        expected = expected_demand_uplift(interest, k)
        for country in COUNTRIES:
            own_event = country in OWN_EVENT_COUNTRIES
            ws.cell(row=row, column=1, value=country)
            ws.cell(row=row, column=2, value=own_event)
            for col, scenario in zip((3, 4, 5), ("low", "base", "high")):
                cell = ws.cell(row=row, column=col, value=interest[scenario]["interest_uplift"] * k)
                cell.number_format = PCT_FORMAT
            cell = ws.cell(row=row, column=6, value=expected)
            cell.number_format = PCT_FORMAT
            row += 1
        row += 1  # blank row between the two k blocks

    widths = {"A": 12, "B": 12, "C": 10, "D": 10, "E": 10, "F": 10}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def write_assumptions_sheet(ws, interest: dict, floor_log: list[tuple]) -> None:
    ws.title = "Assumptions"
    headers = ["Assumption", "Value", "Explanation"]
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = HEADER_FONT

    low, base, high = interest["low"], interest["base"], interest["high"]
    floor_note = " (floored from {:.1f}%)".format(low["raw_net_peak_uplift"] * 100) if low["floored"] else ""
    rows = [
        (
            "Low scenario source",
            f"{low['event_name']} ({low['country']}): {low['interest_uplift'] * 100:.1f}%{floor_note}",
            "Weakest-performing NBA game; net uplift was negative, so it's floored at 0% (see floor rule below)",
        ),
        (
            "Base scenario source",
            f"{base['event_name']} ({base['country']}): {base['interest_uplift'] * 100:.1f}%",
            "Middle-performing NBA game; used as the base case",
        ),
        (
            "High scenario source",
            f"{high['event_name']} ({high['country']}): {high['interest_uplift'] * 100:.1f}%",
            "Best-performing NBA game; used as the upside case",
        ),
        (
            "Negative value floor",
            "0%",
            "A league is unlikely to reduce category demand, so a negative net uplift is treated as no effect, not a decline",
        ),
        (
            "Interest-to-demand conversion (k)",
            "0.25 and 0.5",
            "Share of extra Wikipedia interest assumed to convert to extra purchases; no public data exists, so two values are tested",
        ),
        (
            "Scenario probabilities",
            "low 25%, base 50%, high 25%",
            "Judgement call, not derived from data; weights the three NBA games into one expected case",
        ),
        (
            "Same numbers for all countries",
            "UK, France, Spain, Italy, Germany, Turkey",
            "Only 3 of 6 markets have their own measured game; the data supports a shared European uplift, not country-by-country differences",
        ),
        (
            "Netherlands excluded",
            "n/a",
            "No planned NBA franchise, so not part of the demand plan",
        ),
    ]
    for i, (assumption, value, explanation) in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=assumption)
        ws.cell(row=i, column=2, value=value)
        c = ws.cell(row=i, column=3, value=explanation)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 36
    ws.column_dimensions["C"].width = 70


def write_plan_xlsx(interest: dict, floor_log: list[tuple]) -> None:
    wb = Workbook()
    write_scenarios_sheet(wb.active, interest)
    write_assumptions_sheet(wb.create_sheet(), interest, floor_log)
    wb.save(PLAN_XLSX)


def print_summary(interest: dict, floor_log: list[tuple], scenarios_df: pd.DataFrame) -> None:
    print("=== Scenario inputs (net_peak_uplift, basketball, exposed) ===")
    for scenario, info in interest.items():
        note = " -> FLOORED to 0%" if info["floored"] else ""
        print(
            f"  {scenario:<5} {info['event_name']:<18} ({info['country']}): "
            f"{info['raw_net_peak_uplift'] * 100:+.2f}%{note}"
        )

    if floor_log:
        print("\nFloor applied:")
        for scenario, event_id, event_name, country, raw in floor_log:
            print(f"  {scenario} ({event_id} {event_name}, {country}): {raw * 100:+.2f}% -> 0.0%")

    print("\n=== Expected (probability-weighted) demand uplift ===")
    for k in K_VALUES:
        print(f"  k={k}: {expected_demand_uplift(interest, k) * 100:.2f}%")

    print("\n=== Scenario table (same for all 6 countries) ===")
    for k in K_VALUES:
        print(f"\nk = {k}")
        for scenario in ("low", "base", "high"):
            info = interest[scenario]
            print(
                f"  {scenario:<5} demand_uplift={info['interest_uplift'] * k * 100:+.2f}%  "
                f"(probability={PROBABILITIES[scenario] * 100:.0f}%)"
            )

    print(f"\nRows written to {SCENARIOS_CSV.relative_to(ROOT)}: {len(scenarios_df)}")


def main() -> None:
    interest, floor_log = load_interest_uplifts()
    scenarios_df = build_scenarios_table(interest)
    scenarios_df.to_csv(SCENARIOS_CSV, index=False)
    write_plan_xlsx(interest, floor_log)
    print_summary(interest, floor_log, scenarios_df)


if __name__ == "__main__":
    main()
