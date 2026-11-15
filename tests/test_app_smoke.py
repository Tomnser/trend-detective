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
