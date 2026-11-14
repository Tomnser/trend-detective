"""Shared-cell note and regional 'k of N' summary."""
from __future__ import annotations

from dataclasses import replace

import pytest

from analysis import trend_analysis
from catalogue import PLACES
from challenge import _method_rows, _neighbour_rows, regional_summary
from contracts import ChallengeRow, Plan
from data_access import load_full_series, load_series_for_plan, places_sharing_cell


def test_bergamo_and_milan_share_only_the_merra2_cell():
    assert places_sharing_cell("MERRA2_T2M", "Bergamo") == ["Milan"]
    assert places_sharing_cell("MERRA2_T2M", "Milan") == ["Bergamo"]
    assert places_sharing_cell("MERRA2_T2M", "Po Valley") == []
    for variable in ("GPM_PRECIP", "GLDAS_SSM"):
        for place in PLACES:
            assert places_sharing_cell(variable, place) == []


@pytest.fixture(scope="module")
def milan_gldas_2011():
    lat, lon = PLACES["Milan"]
    plan = Plan("Milan", lat, lon, ["GLDAS_SSM"], "2011-01-01", "2025-12-01")
    full = load_full_series("GLDAS_SSM", "Milan", lat, lon)
    base = trend_analysis(plan, "GLDAS_SSM", load_series_for_plan(plan), reference_series=full)
    return plan, full, base, _neighbour_rows(plan, "GLDAS_SSM", full)


def test_regional_summary_counts(milan_gldas_2011):
    # Milan baseline, north and west are significant decreases; south and east are not (robustness report).
    _, _, base, region = milan_gldas_2011
    text = regional_summary(region, base)
    print("\n" + text)
    assert text.startswith("3 of 5 cells significant")
    assert "not independent confirmations" in text


def test_descriptive_only_is_never_counted(milan_gldas_2011):
    plan, full, base, region = milan_gldas_2011
    sen_row = _method_rows(plan, "GLDAS_SSM", full, base)[2]
    assert sen_row.result.verdict == "descriptive only"
    descriptive_region = ChallengeRow("region", "fake", replace(region[0].result, verdict="descriptive only"), "")
    unavailable = ChallengeRow("region", "fake", None, "Unavailable")
    rows = region + [sen_row, descriptive_region, unavailable]
    assert regional_summary(rows, base).startswith("3 of 5 cells significant")
    # A descriptive-only baseline is not counted either.
    assert regional_summary(region, replace(base, verdict="descriptive only")).startswith("2 of 4 cells significant")
