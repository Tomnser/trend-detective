"""Robustness report for the GLDAS soil-moisture and GPM precipitation results (cache only).

Part 1: every configured date window, each preset place + its 4 grid neighbours (GLDAS).
Part 2: leave-one-year-out, GLDAS, window 2011-2025.
Part 3: Part 1 for GPM precipitation.

Run offline:  EDL_TOKEN= .venv/bin/python scripts/robustness_check.py | tee scripts/robustness_report.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import trend_analysis  # noqa: E402
from catalogue import LAST_YEAR, get_variable_meta  # noqa: E402
from challenge import MIN_FULL_YEARS, date_start_years, grid_step  # noqa: E402
from contracts import Plan  # noqa: E402
from data_access import load_full_series  # noqa: E402
from processing import coverage, coverage_ok  # noqa: E402

PLACES = {"Milan": (45.4642, 9.19), "Bergamo": (45.6983, 9.6773), "Po Valley": (45.0, 10.0)}
DIRECTIONS = (("north", 1, 0), ("south", -1, 0), ("east", 0, 1), ("west", 0, -1))
END = f"{LAST_YEAR}-12-01"


def cells(variable: str) -> list[tuple[str, float, float, pd.Series]]:
    """(name, lat, lon, full record) for each place and its 4 neighbours, as in challenge.py."""
    out = []
    for place, (lat, lon) in PLACES.items():
        full = load_full_series(variable, place, lat, lon)
        a = full.attrs
        out.append((f"{place} (cell {a['cell_lat']}, {a['cell_lon']})", lat, lon, full))
        for direction, s_lat, s_lon in DIRECTIONS:
            t_lat = round(a["cell_lat"] + s_lat * grid_step(a["lat_res"]), 4)
            t_lon = round(a["cell_lon"] + s_lon * grid_step(a["lon_res"]), 4)
            nb = load_full_series(variable, place, t_lat, t_lon)
            out.append((f"  {place} {direction} (cell {nb.attrs['cell_lat']}, {nb.attrs['cell_lon']})", t_lat, t_lon, nb))
    return out


def fit(variable: str, lat: float, lon: float, full: pd.Series, start: str, series: pd.Series | None = None):
    plan = Plan("x", lat, lon, [variable], start, END)
    window = full.reindex(pd.date_range(start, END, freq="MS")) if series is None else series
    return trend_analysis(plan, variable, window, reference_series=full), window


def sign_agrees(r) -> str:
    return "agree" if r.sen_per_decade != 0 and np.sign(r.sen_per_decade) == np.sign(r.slope_per_decade) else "DISAGREE"


def window_table(variable: str, title: str) -> None:
    meta = get_variable_meta(variable)
    unit = meta["display_unit"]
    print(f"\n{'=' * 150}\n{title}: {meta['label']} ({unit} per decade), end {END[:7]}\n{'=' * 150}")
    all_cells = cells(variable)
    for year in date_start_years(meta["first_year"]):
        start = f"{year}-01-01"
        n_full = coverage(full_window := all_cells[0][3].reindex(pd.date_range(start, END, freq="MS")))["full_years"]
        rule = "" if n_full >= MIN_FULL_YEARS else f"   [BELOW the 10-complete-year rule: {n_full} complete years; the app skips this window]"
        print(f"\n-- window {year}-01 to {END[:7]}{rule}")
        print(f"{'cell':44} {'slope/dec':>9} {'95% CI':>19} {'p':>9} {'hac_p':>9} {'Sen':>8} {'Sen vs OLS':>10}  verdict")
        sig_cells, seen = set(), {}
        for name, lat, lon, full in all_cells:
            r, _ = fit(variable, lat, lon, full, start)
            cell = (full.attrs["cell_lat"], full.attrs["cell_lon"])
            if r.verdict.startswith("significant"):
                sig_cells.add(cell)
            flag = "  <- hac_p disagrees" if (r.hac_p < 0.05) != (r.p < 0.05) else ""
            if cell in seen:
                flag += f"  [same cell as {seen[cell]}]"
            seen.setdefault(cell, name.strip().split(" (")[0])
            print(f"{name:44} {r.slope_per_decade:+9.3f} ({r.ci[0]:+8.3f},{r.ci[1]:+8.3f}) {r.p:9.3g} {r.hac_p:9.3g} "
                  f"{r.sen_per_decade:+8.3f} {sign_agrees(r):>10}  {r.verdict}{flag}")
        print(f"   {len(sig_cells)} of {len(seen)} distinct cells significant ({len(all_cells)} rows; repeated cells counted once; "
              "cells are spatially correlated; counts are not independent confirmations)")


def leave_one_year_out(variable: str, start_year: int = 2011) -> None:
    meta = get_variable_meta(variable)
    start = f"{start_year}-01-01"
    years = list(range(start_year, LAST_YEAR + 1))
    print(f"\n{'=' * 150}\nPART 2 · leave-one-year-out: {meta['label']}, window {start_year}-01 to {END[:7]} "
          f"({len(years)} fits per cell; dropped year's 12 months set to NaN, full-record climatology fixed)\n{'=' * 150}")
    print(f"{'cell':44} {'all years':>22} {'slope range (15 fits)':>22} {'p<0.05':>7} {'coverage_ok':>12}  dropped years that flip the verdict")
    for name, lat, lon, full in cells(variable):
        base, window = fit(variable, lat, lon, full, start)
        slopes, n_sig, flips, rejected = [], 0, [], []
        for y in years:
            s = window.copy()
            s[s.index.year == y] = np.nan
            ok, cov = coverage_ok(s)
            if not ok:
                rejected.append(f"{y} ({cov['full_years']} complete yrs)")
            r, _ = fit(variable, lat, lon, full, start, series=s)
            slopes.append(r.slope_per_decade)
            n_sig += r.p < 0.05
            if r.verdict != base.verdict:
                flips.append(f"{y}->{r.verdict.replace('significant ', 'sig ').replace('not enough evidence', 'n.s.')} (p={r.p:.3f})")
        cov_text = "all pass" if not rejected else "REJECTS " + ", ".join(rejected)
        base_text = f"{base.slope_per_decade:+.3f} p={base.p:.3f}"
        print(f"{name:44} {base_text:>22} {min(slopes):+9.3f} to {max(slopes):+8.3f} {n_sig:>4}/15 {cov_text:>12}  "
              f"{', '.join(flips) if flips else 'none'}")


def main() -> None:
    pd.set_option("display.width", 160)
    window_table("GLDAS_SSM", "PART 1 · all configured windows")
    leave_one_year_out("GLDAS_SSM", 2011)
    window_table("GPM_PRECIP", "PART 3 · all configured windows")


if __name__ == "__main__":
    main()
