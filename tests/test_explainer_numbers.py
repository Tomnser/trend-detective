"""Explainer numbers in TrendResult.settings (task C4): consistent with the result itself."""
from __future__ import annotations

import json

import pytest

from analysis import trend_analysis
from contracts import Plan
from data_access import load_full_series


def test_explainer_numbers_milan():
    full = load_full_series("MERRA2_T2M", "Milan", 45.46, 9.19)
    plan = Plan("Milan", 45.46, 9.19, ["MERRA2_T2M"], "1981-01-01", "2025-12-01")
    r = trend_analysis(plan, "MERRA2_T2M", full, reference_series=full)
    e = r.settings["explainer"]
    print("\n" + json.dumps(e, indent=2))
    assert list(e) == ["raw", "seasonal", "fit", "uncertainty"]
    assert (e["raw"]["months"], e["raw"]["months_missing"]) == (540, 0)
    assert len(e["seasonal"]["climatology"]) == 12
    assert e["seasonal"]["anomaly_sd"] < e["raw"]["sd"]  # removing the seasonal cycle shrinks the spread
    # ROADMAP reference: +0.489 °C per decade, about 2.2 °C in total.
    assert e["fit"]["slope_per_decade"] == pytest.approx(0.489, abs=0.0005)
    assert e["fit"]["total_change"] == pytest.approx(2.2, abs=0.05)
    # Same numbers as the result fields: the explainer never tells a different story.
    assert e["fit"]["slope_per_decade"] == r.slope_per_decade
    u = e["uncertainty"]
    assert (u["p"], u["ci_low"], u["ci_high"]) == (r.p, r.ci[0], r.ci[1])
    assert (u["months_used"], u["effective_months"], u["lag1_autocorrelation"]) == (r.n, r.n_eff, r.r1)
    assert u["adjusted_se_per_decade"] >= u["naive_se_per_decade"]
