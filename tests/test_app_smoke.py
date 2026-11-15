"""App smoke test: load the app, click each example, press "Check the finding"."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SUBMIT = "Check the finding"


def _load(monkeypatch) -> AppTest:
    # Empty token: a cache miss becomes a visible error instead of a live NASA call.
    monkeypatch.setenv("EDL_TOKEN", "")
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def test_app_loads_with_examples(monkeypatch):
    at = _load(monkeypatch)
    labels = [b.label for b in at.button]
    assert SUBMIT in labels
    assert len(labels) >= 4, labels  # at least three examples + submit


def test_each_example_runs(monkeypatch):
    examples = [b.label for b in _load(monkeypatch).button if b.label != SUBMIT]
    for label in examples:
        at = _load(monkeypatch)
        _button(at, label).click().run()
        assert not at.exception, (label, at.exception)
        _button(at, SUBMIT).click().run()
        assert not at.exception, (label, at.exception)
        assert not at.error, (label, [e.value for e in at.error])
        plan = at.session_state["applied"]["plan"]
        print(f"{label!r}: {plan.place} · {plan.variables[0]} · {plan.start[:7]}..{plan.end[:7]} ok")


def test_prediction_feedback(monkeypatch):
    expected = {"Rising": "The data support your prediction", "Falling": "The data point the other way",
                "No clear trend": "The data show a likely increase"}
    for choice, feedback in expected.items():
        at = _load(monkeypatch)
        _button(at, "How much has Milan warmed?").click().run()
        next(r for r in at.radio if r.label == "Your prediction").set_value(choice)
        _button(at, SUBMIT).click().run()
        assert not at.exception, at.exception
        infos = [i.value for i in at.info]
        assert len(infos) == 1 and infos[0].startswith(f"Your prediction: {choice}. {feedback}."), infos


def _custom(at: AppTest, lat: float, lon: float, theme: str = "temperature") -> AppTest:
    next(s for s in at.selectbox if s.label == "Where?").set_value("Custom coordinates").run()
    next(s for s in at.selectbox if s.label == "Theme?").set_value(theme).run()
    next(n for n in at.number_input if n.label.startswith("Latitude")).set_value(lat)
    next(n for n in at.number_input if n.label.startswith("Longitude")).set_value(lon).run()
    return at


def test_custom_point_runs_and_loads_nearby_cells_on_demand(monkeypatch):
    from catalogue import PLACES
    lat, lon = PLACES["Milan"]  # cached point: no download
    at = _custom(_load(monkeypatch), lat, lon)
    _button(at, SUBMIT).click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    bundle = at.session_state["applied"]
    assert bundle["plan"].place == f"Custom point {lat:.2f}, {lon:.2f}"
    assert not any(r.check == "region" for r in bundle["challenges"])  # no neighbour downloads yet
    _button(at, "Check the 4 nearby cells (4 NASA downloads)").click().run()
    assert not at.exception, at.exception
    assert sum(r.check == "region" for r in at.session_state["applied"]["challenges"]) == 4


def test_custom_point_over_water_shows_a_clear_message(monkeypatch, tmp_path):
    import data_access
    from tests.test_any_point import SEA_CSV
    monkeypatch.setattr(data_access, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data_access, "fetch_csv", lambda *a, **k: SEA_CSV)
    data_access._full_series_cached.cache_clear()
    at = _custom(_load(monkeypatch), 40.0, 6.0, theme="soil moisture")
    _button(at, SUBMIT).click().run()
    data_access._full_series_cached.cache_clear()
    assert not at.exception, at.exception
    errors = [e.value for e in at.error]
    print("\n", errors)
    assert len(errors) == 1 and "has no data at 40.00, 6.00" in errors[0] and "Choose another point" in errors[0]
    assert "applied" not in at.session_state
