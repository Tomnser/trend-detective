"""Growing-season trend (task E2, engine half) against the reference numbers in ROADMAP.md."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis import season_trend
from catalogue import PLACES
from data_access import load_full_series

APR_SEP = [4, 5, 6, 7, 8, 9]


def _po(variable: str) -> pd.Series:
    lat, lon = PLACES["Po Valley"]
    return load_full_series(variable, "Po Valley", lat, lon)


def test_po_valley_rain_growing_season():
    r = season_trend(_po("GPM_PRECIP"), APR_SEP, "sum")
    s = r.settings
    by_year = dict(zip(s["years"], s["values"]))
    rank = dict(zip(s["years"], s["rank_from_lowest"]))
    print(f"\nPo Valley rain Apr-Sep: {r.n} seasons {s['years'][0]}-{s['years'][-1]}, {r.slope_per_decade:+.1f} mm/decade "
          f"({r.ci[0]:+.1f}, {r.ci[1]:+.1f}), p={r.p:.2f}, {r.verdict}; Sen {r.sen_per_decade:+.1f}; "
          f"leave-one-out {s['leave_one_out_min']:+.1f} (without {s['leave_one_out_min_year']}) to "
          f"{s['leave_one_out_max']:+.1f} (without {s['leave_one_out_max_year']}); "
          f"2022 = {by_year[2022]:.0f} mm, rank {rank[2022]}; mean {s['mean']:.0f} mm; r1 {r.r1:+.2f}")
    assert (r.n, s["years"][0], s["years"][-1], s["years_skipped"]) == (25, 2001, 2025, [])
    assert r.slope_per_decade == pytest.approx(22.4, abs=0.05)
    assert r.p == pytest.approx(0.40, abs=0.005) and r.verdict == "not enough evidence"
    assert by_year[2022] == pytest.approx(352, abs=0.5) and rank[2022] == 2
    assert s["mean"] == pytest.approx(481, abs=0.5)
    assert s["leave_one_out_min"] <= r.slope_per_decade <= s["leave_one_out_max"]
    assert r.ci[0] < 0 < r.ci[1]


def test_po_valley_soil_moisture_growing_season():
    r = season_trend(_po("GLDAS_SSM"), APR_SEP, "mean")
    rank = dict(zip(r.settings["years"], r.settings["rank_from_lowest"]))
    print(f"\nPo Valley soil moisture Apr-Sep mean: {r.n} seasons, {r.slope_per_decade:+.2f}/decade, p={r.p:.2f}, 2022 rank {rank[2022]}")
    assert r.n == 25 and rank[2022] == 2


def test_incomplete_seasons_are_skipped_not_filled():
    s = _po("GPM_PRECIP").copy()
    s.loc["2010-06-01"] = np.nan
    r = season_trend(s, APR_SEP, "sum")
    assert r.n == 24 and r.settings["years_skipped"] == [2010] and 2010 not in r.settings["years"]
    with pytest.raises(ValueError, match="at least 10"):
        season_trend(s.loc["2017":], APR_SEP, "sum")


def test_no_trend_simulation_25_years():
    rng = np.random.default_rng(20261115)
    index = pd.date_range("2001-01-01", "2025-12-01", freq="MS")
    hits = sum(season_trend(pd.Series(rng.gamma(2.0, 40.0, len(index)), index=index), APR_SEP, "sum").p < 0.05
               for _ in range(1000))
    print(f"\nNo-trend simulation, 25 seasons, 1000 series: false-positive rate {hits / 1000:.1%}")
    assert 0.03 <= hits / 1000 <= 0.07


@pytest.mark.parametrize("months", [[11, 12, 1, 2, 3], [4, 6]])
def test_season_must_be_one_consecutive_run(months):
    with pytest.raises(ValueError, match="one consecutive run within a calendar year"):
        season_trend(_po("GPM_PRECIP"), months, "sum")
