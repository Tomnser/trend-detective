"""Growing-season panel (task E2, interface half): renders a season_trend result on its own."""
from __future__ import annotations

from dataclasses import replace

from streamlit.testing.v1 import AppTest

from analysis import season_trend
from catalogue import PLACES
from contracts import Plan
from data_access import load_full_series
from panels.season import season_unit, sentence


def _script(variable: str, how: str):
    from analysis import season_trend
    from catalogue import PLACES
    from contracts import Plan
    from data_access import load_full_series
    from panels.season import render

    lat, lon = PLACES["Po Valley"]
    plan = Plan("Po Valley", lat, lon, [variable], "2001-01-01", "2025-12-01", mode="farmer", season=[4, 5, 6, 7, 8, 9])
    result = season_trend(load_full_series(variable, "Po Valley", lat, lon), plan.season, how)
    render({"plan": plan, "result": result})


def _text(at: AppTest) -> str:
    parts = [e.value for group in (at.subheader, at.markdown, at.caption) for e in group]
    parts += [f"{m.label}: {m.value}" for m in at.metric]
    return "\n".join(parts)


def test_po_valley_rain_panel(monkeypatch):
    monkeypatch.setenv("EDL_TOKEN", "")
    at = AppTest.from_function(_script, args=("GPM_PRECIP", "sum"), default_timeout=60).run()
    assert not at.exception, at.exception
    text = _text(at)
    print("\n" + text)
    assert ("2022 was the 2nd driest growing season of 25. An extreme year is not a trend: "
            "the 25 seasons show none (p = 0.40).") in text
    assert "April–September total" in text and "Seasons used: 25" in text
    assert "mm/month" not in text  # a summed season is in mm
    assert "HAC" not in text and "Effective months" not in text and "nan" not in text.lower()


def test_soil_moisture_panel_keeps_the_unit(monkeypatch):
    monkeypatch.setenv("EDL_TOKEN", "")
    at = AppTest.from_function(_script, args=("GLDAS_SSM", "mean"), default_timeout=60).run()
    assert not at.exception, at.exception
    assert "April–September mean" in _text(at) and "mm water (top 10 cm)" in _text(at)


def test_sentence_follows_the_result():
    lat, lon = PLACES["Po Valley"]
    r = season_trend(load_full_series("GPM_PRECIP", "Po Valley", lat, lon), [4, 5, 6, 7, 8, 9], "sum")
    assert sentence(r, 2003).startswith("2003 was the driest growing season of 25.")
    assert sentence(r, 1990) == "An extreme year is not a trend: the 25 seasons show none (p = 0.40)."
    up = replace(r, verdict="significant increase", p=0.003)
    assert sentence(up, 2022).endswith("Taken together, the 25 seasons show a likely increase (p < 0.01).")
    assert (season_unit("GPM_PRECIP", "sum"), season_unit("GPM_PRECIP", "mean")) == ("mm", "mm/month")
