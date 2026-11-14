"""The three method rows (OLS, HAC, seasonal Sen) must show different things."""
from __future__ import annotations

import math

import pytest

from analysis import trend_analysis
from challenge import _method_rows
from contracts import Plan
from data_access import load_full_series, load_series_for_plan


@pytest.fixture(scope="module")
def milan_2016():
    plan = Plan("Milan", 45.46, 9.19, ["MERRA2_T2M"], "2016-01-01", "2025-12-01")
    full = load_full_series("MERRA2_T2M", "Milan", 45.46, 9.19)
    base = trend_analysis(plan, "MERRA2_T2M", load_series_for_plan(plan), reference_series=full)
    return base, _method_rows(plan, "MERRA2_T2M", full, base)


def test_method_rows_differ(milan_2016):
    base, rows = milan_2016
    ols, hac, sen = (r.result for r in rows)
    print(f"\nOLS: {ols.slope_per_decade:+.3f} ({ols.ci[0]:+.3f},{ols.ci[1]:+.3f}) p={ols.p:.3g} {ols.verdict}"
          f"\nHAC: {hac.slope_per_decade:+.3f} ({hac.ci[0]:+.3f},{hac.ci[1]:+.3f}) p={hac.p:.3g} {hac.verdict}"
          f"\nSen: {sen.slope_per_decade:+.3f} {sen.verdict} · {rows[2].label}")
    keys = [(r.slope_per_decade, r.ci, r.p, r.verdict) for r in (ols, hac, sen)]
    assert len({repr(k) for k in keys}) == 3

    assert ols is base
    # HAC row: OLS slope, HAC interval / p / verdict.
    assert hac.slope_per_decade == base.slope_per_decade
    assert hac.p == base.hac_p and hac.ci == base.hac_ci
    assert hac.verdict == "significant increase" and ols.verdict == "not enough evidence"
    assert (hac.ci[0] > 0) == (hac.p < 0.05)  # interval and p-value use the same normal distribution
    # Sen row: Sen slope, sign agreement, no significance test.
    assert sen.slope_per_decade == pytest.approx(0.689, abs=0.001)
    assert sen.verdict == "descriptive only"
    assert math.isnan(sen.p) and math.isnan(sen.ci[0]) and math.isnan(sen.hac_p)
    assert "agrees in sign with OLS" in rows[2].label


def test_sen_row_full_record_value():
    plan = Plan("Milan", 45.46, 9.19, ["MERRA2_T2M"], "1981-01-01", "2025-12-01")
    full = load_full_series("MERRA2_T2M", "Milan", 45.46, 9.19)
    base = trend_analysis(plan, "MERRA2_T2M", load_series_for_plan(plan), reference_series=full)
    sen = _method_rows(plan, "MERRA2_T2M", full, base)[2].result
    assert sen.slope_per_decade == pytest.approx(0.482, abs=0.001)
