"""Calibration grid (task C6): false-positive rates of the engine's two p-values under no trend.

Synthetic monthly series: a seasonal cycle plus AR(1) noise, no trend (the same generator as
tests/test_null_simulation.py). For each record length and lag-1 autocorrelation, the share of
series the engine calls significant at 0.05. A calibrated test gives 5%.
Run: python scripts/calibration_grid.py   (offline, about 2 minutes; writes scripts/calibration_grid.txt)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import trend_analysis  # noqa: E402
from contracts import Plan  # noqa: E402

N_SIM = 1000
ALPHA = 0.05
SEED = 20261114
YEARS = (10, 15, 25, 35, 45)
PHIS = (0.2, 0.5, 0.8)
OUT = ROOT / "scripts" / "calibration_grid.txt"


def simulate(rng: np.random.Generator, index: pd.DatetimeIndex, phi: float) -> pd.Series:
    e = np.zeros(len(index) + 100)
    for t in range(1, len(e)):
        e[t] = phi * e[t - 1] + rng.normal()
    seasonal = 8.0 * np.sin(2 * np.pi * (index.month - 1) / 12)
    return pd.Series(seasonal + e[100:], index=index)


def main() -> None:
    rng = np.random.default_rng(SEED)
    se = np.sqrt(ALPHA * (1 - ALPHA) / N_SIM)
    lines = [f"Calibration grid: {N_SIM} no-trend series per cell, seasonal cycle + AR(1) noise, seed {SEED}.",
             f"False-positive rate at {ALPHA} (a calibrated test gives 5.0%; Monte Carlo SE about {se:.1%}).",
             "", f"{'years':>5} {'lag-1':>6} {'adjusted OLS (verdict)':>23} {'HAC, 12-month lag':>19}"]
    rates = []
    for years in YEARS:
        index = pd.date_range("1981-01-01", periods=12 * years, freq="MS")
        plan = Plan("sim", 0, 0, ["MERRA2_T2M"], "1981-01-01", f"{index[-1]:%Y-%m-%d}")
        for phi in PHIS:
            adj = hac = 0
            for _ in range(N_SIM):
                s = simulate(rng, index, phi)
                r = trend_analysis(plan, "MERRA2_T2M", s, reference_series=s)
                adj += r.p < ALPHA
                hac += r.hac_p < ALPHA
            rates.append((years, phi, adj / N_SIM, hac / N_SIM))
            lines.append(f"{years:>5} {phi:>6.1f} {adj / N_SIM:>23.1%} {hac / N_SIM:>19.1%}")
            print(lines[-1], flush=True)
    t = pd.DataFrame(rates, columns=["years", "phi", "adj", "hac"])
    lines += ["", f"Adjusted OLS, all cells: {t.adj.min():.1%} to {t.adj.max():.1%}."]
    for years in (YEARS[0], YEARS[-1]):
        h = t[t.years == years].hac
        lines.append(f"HAC at {years} years: {h.min():.1%} to {h.max():.1%}.")
    lines.append("Limits: AR(1) noise only. Real series can have longer memory, changing variance or breaks.")
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-5:]))


if __name__ == "__main__":
    main()
