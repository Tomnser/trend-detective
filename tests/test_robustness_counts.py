"""Robustness counts (task C5, engine half): real counts from the challenge rows."""
from __future__ import annotations

import pytest

from analysis import trend_analysis
from catalogue import LAST_YEAR, PLACES, SUPPORTED_VARIABLES
from challenge import build_challenge_rows, robustness_counts
from contracts import Plan
from data_access import load_full_series, load_series_for_plan


def _case(place: str, variable: str, start_year: int | None = None, neighbours: bool = True):
    lat, lon = PLACES[place]
    start = start_year or SUPPORTED_VARIABLES[variable]["first_year"]
    plan = Plan(place, lat, lon, [variable], f"{start}-01-01", f"{LAST_YEAR}-12-01")
    base = trend_analysis(plan, variable, load_series_for_plan(plan, variable),
                          reference_series=load_full_series(variable, place, lat, lon))
    rows = build_challenge_rows(plan, base, neighbours=neighbours)
    return base, rows, robustness_counts(rows, base)


def test_milan_temperature_counts():
    base, rows, c = _case("Milan", "MERRA2_T2M")
    print("\nMilan temperature: " + c["sentence"])
    # tests/test_milan_table.py: windows from 1981, 1991, 2001, 2011 are significant; 2016 is not (p = 0.0544).
    assert (c["windows_total"], c["windows_same_direction"], c["windows_significant"]) == (5, 5, 4)
    assert c["cells_total"] == 4 and c["baseline_significant"]
    assert not any(r.check == "coverage" for r in rows)  # the two coverage rows are gone


def test_counts_match_the_rows():
    base, rows, c = _case("Po Valley", "GPM_PRECIP")
    print("\nPo Valley rain: " + c["sentence"])
    for key, check in (("windows", "date"), ("cells", "region")):
        results = [r.result for r in rows if r.check == check and r.result is not None]
        same = [r for r in results if r.slope_per_decade * base.slope_per_decade > 0]
        assert c[f"{key}_total"] == len(results)
        assert c[f"{key}_same_direction"] == len(same)
        assert c[f"{key}_significant"] == sum(r.verdict.startswith("significant") for r in same)
        assert c[f"{key}_significant"] <= c[f"{key}_same_direction"] <= c[f"{key}_total"]


def test_sentence_without_nearby_cells():
    _, _, c = _case("Milan", "MERRA2_T2M", neighbours=False)
    assert c["cells_total"] == 0 and "nearby cells" not in c["sentence"].split(". Nearby")[0]
    assert c["sentence"].startswith("The direction holds in 5 of 5 date windows. It is significant in 4 of 5 date windows.")
