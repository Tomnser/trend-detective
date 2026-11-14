"""Real Milan MERRA-2 temperature: engine results for several start years (cache only)."""
from __future__ import annotations

import pytest

from analysis import trend_analysis
from contracts import Plan
from data_access import load_full_series

START_YEARS = (1981, 1991, 2001, 2011, 2016)


def milan_table() -> dict[int, object]:
    full = load_full_series("MERRA2_T2M", "Milan", 45.46, 9.19)
    out = {}
    for y in START_YEARS:
        plan = Plan("Milan", 45.46, 9.19, ["MERRA2_T2M"], f"{y}-01-01", "2025-12-01")
        out[y] = trend_analysis(plan, "MERRA2_T2M", full[f"{y}-01-01":"2025-12-01"], reference_series=full)
    return out


def test_milan_table():
    table = milan_table()
    print(f"\n{'start':>5} {'slope/dec':>9} {'95% CI':>17} {'p':>9} {'hac_p':>9} {'Sen':>6} {'yrs needed':>10}  verdict")
    for y, r in table.items():
        print(f"{y:>5} {r.slope_per_decade:+9.3f} ({r.ci[0]:+.3f},{r.ci[1]:+.3f}) {r.p:9.3g} {r.hac_p:9.3g} "
              f"{r.sen_per_decade:+6.3f} {r.years_needed:10.1f}  {r.verdict}")
        for w in r.warnings[3:]:
            print(f"      warning: {w}")
    a, b = table[1981], table[2016]
    assert a.slope_per_decade == pytest.approx(0.49, abs=0.01)
    assert a.verdict == "significant increase"
    assert b.slope_per_decade == pytest.approx(0.94, abs=0.01)
    assert b.p == pytest.approx(0.054, abs=0.002)
    assert b.verdict == "not enough evidence"
    assert b.hac_p == pytest.approx(0.02, abs=0.002)
