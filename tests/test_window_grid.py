"""Window grid (task C1) against the reference numbers in ROADMAP.md."""
from __future__ import annotations

import pytest

from catalogue import PLACES
from challenge import WINDOW_GRID_COLUMNS, window_grid
from contracts import Plan

UP, DOWN = "significant increase", "significant decrease"


def _grid(place: str, variable: str):
    lat, lon = PLACES[place]
    # The plan's own dates must not matter: the grid always covers the full record.
    return window_grid(Plan(place, lat, lon, [variable], "2010-01-01", "2015-12-01"), variable)


def _row(grid, start: int, end: int):
    return grid[(grid["start"] == start) & (grid["end"] == end)].iloc[0]


@pytest.mark.parametrize("place, variable, n, n_sig, n_down, n_up, n_bh", [
    ("Po Valley", "GPM_PRECIP", 135, 19, 8, 11, 1),
    ("Po Valley", "GLDAS_SSM", 136, 17, 15, 2, 1),
    ("Milan", "MERRA2_T2M", 666, 416, 0, 416, 372),
])
def test_window_counts(place, variable, n, n_sig, n_down, n_up, n_bh):
    g = _grid(place, variable)
    print(f"\n{place} {variable}: {len(g)} windows, {(g.p < 0.05).sum()} significant "
          f"({(g.verdict == DOWN).sum()} down, {(g.verdict == UP).sum()} up), {g.significant_bh.sum()} after BH")
    assert list(g.columns) == WINDOW_GRID_COLUMNS
    assert len(g) == n and not g.duplicated(["start", "end"]).any()
    assert (g.p < 0.05).sum() == n_sig
    assert ((g.verdict == DOWN).sum(), (g.verdict == UP).sum()) == (n_down, n_up)
    assert g.significant_bh.sum() == n_bh
    assert (g.ci_low <= g.slope).all() and (g.slope <= g.ci_high).all()


def test_po_valley_rain_windows():
    g = _grid("Po Valley", "GPM_PRECIP")
    assert g.slope.min() == pytest.approx(-39.3, abs=0.05) and g.slope.max() == pytest.approx(53.8, abs=0.05)
    r = _row(g, 2013, 2022)
    assert r.slope == pytest.approx(-39.3, abs=0.05) and r.p == pytest.approx(0.024, abs=0.0005) and r.verdict == DOWN
    r = _row(g, 2001, 2022)
    assert r.slope == pytest.approx(0.0, abs=0.05) and r.p == pytest.approx(0.998, abs=0.0005)
    r = _row(g, 2001, 2025)  # the last year is partial (rain ends 2025-09)
    assert r.slope == pytest.approx(4.4, abs=0.05) and r.p == pytest.approx(0.32, abs=0.005)
    assert g[g.significant_bh].verdict.tolist() == [UP]
