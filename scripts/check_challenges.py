"""Phase 3 checks: challenge tables with real data (also fills the neighbour cache)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import trend_analysis  # noqa: E402
from catalogue import LAST_YEAR, SUPPORTED_VARIABLES, get_variable_meta  # noqa: E402
from challenge import build_challenge_rows  # noqa: E402
from contracts import Plan  # noqa: E402
from data_access import load_full_series, load_series_for_plan  # noqa: E402

PLACES = {"Milan": (45.4642, 9.19), "Po Valley": (45.0, 10.0), "Bergamo": (45.6983, 9.6773)}


def run(place: str, variable: str, verbose: bool) -> list[str]:
    lat, lon = PLACES[place]
    meta = get_variable_meta(variable)
    plan = Plan(place, lat, lon, [variable], f"{meta['first_year']}-01-01", f"{LAST_YEAR}-12-01")
    full = load_full_series(variable, place, lat, lon)
    base = trend_analysis(plan, variable, load_series_for_plan(plan, variable), reference_series=full)
    t0 = time.perf_counter()
    rows = build_challenge_rows(plan, base)
    dt = time.perf_counter() - t0
    problems = []
    dates = [r.label for r in rows if r.check == "date"]
    if len(dates) != len(set(dates)):
        problems.append(f"duplicate date rows: {dates}")
    region = [r for r in rows if r.check == "region"]
    cells = [r.label.split("(cell ")[-1].rstrip(")") for r in region if r.result is not None]
    if len(region) != 4 or len(cells) != len(set(cells)) or len(cells) != 4:
        problems.append(f"neighbours: {[(r.label, r.note if r.result is None else 'ok') for r in region]}")
    print(f"\n=== {place} · {variable} · baseline cell {full.attrs['cell_lat']}, {full.attrs['cell_lon']} "
          f"(grid {full.attrs['lat_res']}×{full.attrs['lon_res']}) · challenges in {dt:.1f} s")
    for r in rows if verbose else [r for r in rows if r.check in ("date", "region")]:
        if r.result is None:
            print(f"  {r.check:8} {r.label:46} UNAVAILABLE: {r.note}")
            continue
        x = r.result
        extra = f" passes={x.settings.get('coverage_passes_variant')}" if r.check == "coverage" else ""
        print(f"  {r.check:8} {r.label:46} {x.slope_per_decade:+8.3f} ({x.ci[0]:+8.3f},{x.ci[1]:+8.3f}) "
              f"p={x.p:<9.3g} hac_p={x.hac_p:<9.3g} cov={x.coverage:6.1%} {x.verdict}{extra}")
    return [f"{place}/{variable}: {p}" for p in problems]


def main() -> None:
    problems = run("Milan", "MERRA2_T2M", verbose=True)
    for variable in SUPPORTED_VARIABLES:
        for place in PLACES:
            if (place, variable) != ("Milan", "MERRA2_T2M"):
                problems += run(place, variable, verbose=False)
    print("\nPROBLEMS:", problems or "none")


if __name__ == "__main__":
    main()
