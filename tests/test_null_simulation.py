"""False-positive rates under no trend: seasonal cycle + AR(1) noise (phi = 0.5).

Run with `pytest -s` to see the report.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis import trend_analysis
from contracts import Plan
from processing import anomaly_series, climatology_for

N_SIM = 500
PHI = 0.5
ALPHA = 0.05
SEED = 20261114
INDEX = pd.date_range("1981-01-01", "2025-12-01", freq="MS")  # 45 years, 540 months


def simulate(rng: np.random.Generator) -> pd.Series:
    e = np.zeros(len(INDEX) + 100)
    for t in range(1, len(e)):
        e[t] = PHI * e[t - 1] + rng.normal()
    seasonal = 8.0 * np.sin(2 * np.pi * (INDEX.month - 1) / 12)
    return pd.Series(seasonal + e[100:], index=INDEX)


def naive_ols_p(anomalies: pd.Series) -> float:
    x = np.arange(len(anomalies)) / 12.0
    return float(stats.linregress(x, anomalies.to_numpy()).pvalue)


def seasonal_mann_kendall_p(anomalies: pd.Series) -> float:
    """Hirsch et al. (1982) seasonal Mann–Kendall, no ties correction; test-only, not used by the app."""
    s_total, var_total = 0.0, 0.0
    for month in range(1, 13):
        v = anomalies[anomalies.index.month == month].dropna().to_numpy()
        n = len(v)
        s_total += np.sign(v[None, :] - v[:, None])[np.triu_indices(n, 1)].sum()
        var_total += n * (n - 1) * (2 * n + 5) / 18.0
    z = (s_total - np.sign(s_total)) / np.sqrt(var_total)
    return float(2 * stats.norm.sf(abs(z)))


def test_null_false_positive_rates():
    rng = np.random.default_rng(SEED)
    plan = Plan("sim", 0, 0, ["MERRA2_T2M"], "1981-01-01", "2025-12-01")
    hits = {"naive OLS": 0, "adjusted OLS (engine p)": 0, "HAC (engine hac_p)": 0, "seasonal Mann-Kendall": 0}
    for _ in range(N_SIM):
        s = simulate(rng)
        anomalies = anomaly_series(s, climatology_for(s))
        r = trend_analysis(plan, "MERRA2_T2M", s, reference_series=s)
        hits["naive OLS"] += naive_ols_p(anomalies) < ALPHA
        hits["adjusted OLS (engine p)"] += r.p < ALPHA
        hits["HAC (engine hac_p)"] += r.hac_p < ALPHA
        hits["seasonal Mann-Kendall"] += seasonal_mann_kendall_p(anomalies) < ALPHA
    rates = {k: v / N_SIM for k, v in hits.items()}
    se = np.sqrt(ALPHA * (1 - ALPHA) / N_SIM)
    print(f"\nNull simulation: {N_SIM} series, 45 y monthly, seasonal cycle + AR(1) phi={PHI}, no trend "
          f"(Monte Carlo SE at 5% = {se:.1%})")
    for k, v in rates.items():
        print(f"  {k:26} false-positive rate at 0.05: {v:6.1%}")
    assert rates["adjusted OLS (engine p)"] <= 0.08, "adjusted OLS false-positive rate above 8%"
