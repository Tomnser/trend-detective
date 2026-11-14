"""Cache the D2 presets (task D2). One attempt per call, no retry, and a stated call budget.

Stage 1: baseline cell for each preset x 3 variables, then a coverage table (no trends).
Stage 2: the 4 neighbour cells the challenge check asks for, for each preset x 3 variables.
Run: python scripts/cache_presets.py 1|2   (needs EDL_TOKEN in .env)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalogue import LAST_YEAR, SUPPORTED_VARIABLES  # noqa: E402
from challenge import grid_step  # noqa: E402
from data_access import cache_path, fetch_csv, load_full_series  # noqa: E402
from processing import coverage_ok  # noqa: E402

PRESETS = {
    "Seville": (37.39, -5.99),
    "Niamey": (13.51, 2.11),
    "Fairbanks": (64.84, -147.72),
    "Sierra Nevada": (37.87, -119.35),
    "Murray-Darling Basin": (-34.29, 146.05),
}
BUDGET = {"1": 12, "2": 60}
calls = 0


def ensure(variable: str, lat: float, lon: float, budget: int) -> str:
    """Fetch one series into cache/ unless it is there. Returns 'cached', 'fetched' or an error text."""
    global calls
    meta = SUPPORTED_VARIABLES[variable]
    start, end = f"{meta['first_year']}-01", f"{LAST_YEAR}-12"
    path = cache_path(meta["api_id"], round(lat, 2), round(lon, 2), start, end)
    if path.exists():
        return "cached"
    if calls >= budget:
        sys.exit(f"Call budget of {budget} reached; stopping before another fetch.")
    calls += 1
    try:
        text = fetch_csv(meta["api_id"], round(lat, 2), round(lon, 2), start, end, retries=1)
    except RuntimeError as error:
        return f"FAILED: {str(error)[:160]}"
    path.write_text(text)
    return "fetched"


def coverage_line(variable: str, lat: float, lon: float) -> str:
    try:
        s = load_full_series(variable, "", lat, lon)
    except (RuntimeError, ValueError, OSError) as error:
        return f"NO DATA: {str(error)[:120]}"
    ok, cov = coverage_ok(s)
    a = s.attrs
    return (f"{'ok  ' if ok else 'FAIL'} cell {a['cell_lat']}, {a['cell_lon']}  {int(s.notna().sum())}/{len(s)} months  "
            f"{cov['full_years']} complete years  worst calendar month {cov['min_month_frac']:.0%}")


def main(stage: str) -> None:
    budget = BUDGET[stage]
    t0 = time.perf_counter()
    for place, (lat, lon) in PRESETS.items():
        for variable in SUPPORTED_VARIABLES:
            if stage == "1":
                status = ensure(variable, lat, lon, budget)
                print(f"{place:21s} {variable:11s} {status:8s} {coverage_line(variable, lat, lon)}")
                continue
            a = load_full_series(variable, place, lat, lon).attrs  # baseline must be cached already
            step_lat, step_lon = grid_step(a["lat_res"]), grid_step(a["lon_res"])
            for direction, sy, sx in (("north", 1, 0), ("south", -1, 0), ("east", 0, 1), ("west", 0, -1)):
                nlat, nlon = round(a["cell_lat"] + sy * step_lat, 4), round(a["cell_lon"] + sx * step_lon, 4)
                status = ensure(variable, nlat, nlon, budget)
                print(f"{place:21s} {variable:11s} {direction:5s} {status:8s} {coverage_line(variable, nlat, nlon)}")
    print(f"Live calls made: {calls} of a budget of {budget}, in {time.perf_counter() - t0:.0f} s.")


if __name__ == "__main__":
    main(sys.argv[1])
