"""Evidence line numbers (task B3): smallest detectable trend and capped years needed."""
from __future__ import annotations

import pytest

from analysis import YEARS_NEEDED_CAP, smallest_detectable_trend, trend_analysis, years_to_detect
from catalogue import LAST_YEAR, PLACES, SUPPORTED_VARIABLES
from contracts import Plan
from data_access import load_full_series, load_series_for_plan


def _result(place: str, variable: str):
    lat, lon = PLACES[place]
    plan = Plan(place, lat, lon, [variable], f"{SUPPORTED_VARIABLES[variable]['first_year']}-01-01", f"{LAST_YEAR}-12-01")
    full = load_full_series(variable, place, lat, lon)
    return trend_analysis(plan, variable, load_series_for_plan(plan, variable), reference_series=full)


@pytest.mark.parametrize("sigma, years, phi", [(1.4, 45.0, 0.19), (60.0, 24.75, 0.0), (2.0, 10.0, 0.99), (2.0, 10.0, -0.3)])
def test_inverse_of_years_to_detect(sigma, years, phi):
    # A trend exactly at the detectable size needs exactly the record we have.
    omega = smallest_detectable_trend(sigma, years, phi)
    assert years_to_detect(sigma, omega, phi) == pytest.approx(years)


@pytest.mark.parametrize("place, variable", [("Milan", "GPM_PRECIP"), ("Po Valley", "GLDAS_SSM"), ("Milan", "MERRA2_T2M")])
def test_evidence_settings(place, variable):
    r = _result(place, variable)
    e = r.settings["evidence"]
    unit = SUPPORTED_VARIABLES[variable]["display_unit"]
    print(f"\n{place} {variable}: slope {r.slope_per_decade:+.3f} {unit}/decade, p={r.p:.3f}, {r.verdict}; "
          f"record {e['record_years']:.2f} y; smallest detectable ±{e['smallest_detectable_trend_per_decade']:.3f} {unit}/decade; "
          f"years needed {r.years_needed:.1f} -> shown {e['years_needed_under_cap']}")
    assert e["record_years"] == r.n / 12.0
    assert e["smallest_detectable_trend_per_decade"] > 0
    assert e["years_needed_cap"] == YEARS_NEEDED_CAP == 100.0
    assert e["years_needed_under_cap"] == (r.years_needed if r.years_needed < 100.0 else None)
    # Consistent with years needed: a slope above the detectable size needs fewer years than we have.
    assert (abs(r.slope_per_decade) > e["smallest_detectable_trend_per_decade"]) == (r.years_needed < e["record_years"])
