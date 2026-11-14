"""The hand-written Newey–West p-value in analysis.py must match statsmodels."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from analysis import trend_analysis
from contracts import Plan
from data_access import load_full_series
from processing import anomaly_series, climatology_for


def _engine_inputs(series: pd.Series, reference: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Same x (decimal years) and y (non-missing anomalies) as analysis.trend_analysis."""
    clean = anomaly_series(series, climatology_for(reference)).dropna()
    x = clean.index.year.to_numpy(float) + (clean.index.month.to_numpy(float) - 1) / 12.0
    return x - x.min(), clean.to_numpy(float)


def _statsmodels_hac_p(x: np.ndarray, y: np.ndarray, use_correction: bool) -> float:
    fit = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 12, "use_correction": use_correction})
    return float(fit.pvalues[1])


def _ar1_series(seed: int, phi: float = 0.5, trend_per_year: float = 0.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1981-01-01", "2025-12-01", freq="MS")
    e = np.zeros(len(idx) + 100)
    for t in range(1, len(e)):
        e[t] = phi * e[t - 1] + rng.normal()
    seasonal = 8 * np.sin(2 * np.pi * (idx.month - 1) / 12)
    years = np.arange(len(idx)) / 12.0
    return pd.Series(seasonal + e[100:] + trend_per_year * years, index=idx)


def _cases():
    full = load_full_series("MERRA2_T2M", "Milan", 45.46, 9.19)
    yield "Milan T2M 1981-2025", full, full
    yield "Milan T2M 2016-2025", full["2016-01-01":], full
    for seed, trend in ((1, 0.0), (2, 0.0), (3, 0.02)):
        s = _ar1_series(seed, trend_per_year=trend)
        yield f"synthetic AR(1) seed={seed} trend={trend}/yr", s, s


@pytest.mark.parametrize("name,series,reference", list(_cases()), ids=lambda v: v if isinstance(v, str) else "")
def test_hac_matches_statsmodels(name, series, reference):
    plan = Plan("t", 0, 0, ["MERRA2_T2M"], str(series.index[0].date()), str(series.index[-1].date()))
    ours = trend_analysis(plan, "MERRA2_T2M", series, reference_series=reference).hac_p
    x, y = _engine_inputs(series, reference)
    sm_plain = _statsmodels_hac_p(x, y, use_correction=False)
    sm_default = _statsmodels_hac_p(x, y, use_correction=True)
    print(f"\n{name}: ours={ours:.10g}  statsmodels(no correction)={sm_plain:.10g}  "
          f"diff={abs(ours - sm_plain):.2e}  |  statsmodels default (n/(n-k) correction)={sm_default:.10g}  "
          f"diff={abs(ours - sm_default):.2e}")
    assert abs(ours - sm_plain) < 1e-6
    assert ours == pytest.approx(sm_plain, rel=1e-6)
