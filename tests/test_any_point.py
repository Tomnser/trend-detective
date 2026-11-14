"""Any coordinates (task D3, engine half): clear errors for points without data; neighbours on demand.

Offline: fetch_csv is replaced. The all-missing CSV copies the header of a real Giovanni response
for GLDAS over the sea (40.0, 6.0), where every value is the undef code.
"""
from __future__ import annotations

import pytest

import challenge
import data_access
from analysis import trend_analysis
from catalogue import PLACES
from contracts import Plan
from data_access import NoDataError, load_full_series, load_series_for_plan

SEA_CSV = """prod_name,GLDAS_NOAH025_M.2.1
doi,10.5067/SXAVCZFAQLNO
param_short_name,SoilMoi0_10cm_inst
param_name,Soil moisture content (0 - 10 cm underground)
unit,kg m-2
undef,-9999
lat,40.125
lon,6.125
lat_resolution,0.25
lon_resolution,0.25
Request_time,2026-11-14 21:21:02

Timestamp (UTC),Data
""" + "\n".join(f"{y}-{m:02d}-01 00:00,-9999" for y in range(2001, 2026) for m in range(1, 13))


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(data_access, "CACHE_DIR", tmp_path)
    data_access._full_series_cached.cache_clear()
    yield monkeypatch
    data_access._full_series_cached.cache_clear()


def test_point_over_water_gives_a_clear_message(offline):
    offline.setattr(data_access, "fetch_csv", lambda *a, **k: SEA_CSV)
    with pytest.raises(NoDataError) as info:
        load_full_series("GLDAS_SSM", "sea", 40.0, 6.0)
    print("\n" + str(info.value))
    assert str(info.value) == ("GLDAS soil moisture (0–10 cm) has no data at 40.00, 6.00. This grid cell has no values, "
                               "for example because it is over water or ice. Choose another point.")
    assert (info.value.reason, info.value.lat, info.value.lon) == ("no values", 40.0, 6.0)
    assert isinstance(info.value, ValueError)  # the app's existing handler shows it


def test_point_outside_coverage_gives_a_clear_message(offline):
    class NotFound:
        status_code, text = 404, "Data, GLDAS_NOAH025_M_2_1_SoilMoi0_10cm_inst, was not found for the requested latitude -75.0."

    offline.setenv("EDL_TOKEN", "test-token")
    offline.setattr(data_access.requests, "get", lambda *a, **k: NotFound())
    with pytest.raises(NoDataError) as info:
        load_full_series("GLDAS_SSM", "ice", -75.0, 0.0)
    print("\n" + str(info.value))
    assert str(info.value) == "GLDAS soil moisture (0–10 cm) does not cover the point -75.00, 0.00. Choose another point."
    assert info.value.reason == "outside coverage"


@pytest.mark.parametrize("lat, lon", [(91.0, 0.0), (-90.5, 0.0), (0.0, 181.0), (0.0, -200.0), (float("nan"), 0.0)])
def test_invalid_coordinates_fail_before_any_download(offline, lat, lon):
    def no_call(*a, **k):
        raise AssertionError("a download was attempted")

    offline.setattr(data_access, "fetch_csv", no_call)
    with pytest.raises(ValueError, match="latitude must be between -90 and 90"):
        load_full_series("MERRA2_T2M", "nowhere", lat, lon)


def test_neighbours_false_skips_the_nearby_cells(monkeypatch):
    lat, lon = PLACES["Milan"]
    plan = Plan("Milan", lat, lon, ["GLDAS_SSM"], "2001-01-01", "2025-12-01")
    base = trend_analysis(plan, "GLDAS_SSM", load_series_for_plan(plan), reference_series=load_full_series("GLDAS_SSM", "Milan", lat, lon))
    with_neighbours = challenge.build_challenge_rows(plan, base)

    def no_neighbours(*a, **k):
        raise AssertionError("neighbour cells were requested")

    monkeypatch.setattr(challenge, "_neighbour_rows", no_neighbours)
    without = challenge.build_challenge_rows(plan, base, neighbours=False)
    assert [r.label for r in without] == [r.label for r in with_neighbours if r.check != "region"]
    assert sum(r.check == "region" for r in with_neighbours) == 4
