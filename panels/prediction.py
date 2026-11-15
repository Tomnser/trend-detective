"""B2: capture a prediction and compare it with the unchanged engine verdict."""
from __future__ import annotations
import streamlit as st
from catalogue import get_variable_meta


def render(bundle: dict):
    if bundle.get("stage") == "choose":
        st.markdown("**Before you reveal the result, what do you expect?**")
        return st.radio("Your prediction", ["Rising", "Falling", "No clear trend"], index=None,
                        horizontal=True, key=f"prediction_{bundle['context']}")
    result, prediction = bundle.get("result"), bundle.get("prediction")
    if result is None:
        return
    if prediction is not None:
        st.info(f"Your prediction: {prediction}. {_feedback(prediction, result, bundle)}")


def _feedback(prediction: str, result, bundle: dict) -> str:
    """Compare the guess with the unchanged engine verdict, and say why."""
    unit = get_variable_meta(bundle["plan"].variables[0])["display_unit"]
    slope = f"{result.slope_per_decade:+.2g} {unit} per decade"
    expected = {"Rising": "significant increase", "Falling": "significant decrease"}
    if result.verdict == "not enough evidence":
        lean = "up" if result.slope_per_decade > 0 else "down" if result.slope_per_decade < 0 else "nowhere"
        if prediction == "No clear trend":
            text = (f"Not enough evidence either way. That matches your guess: the best estimate leans {lean} "
                    f"({slope}), but the uncertainty is too large to confirm a direction.")
        else:
            text = (f"Not enough evidence either way. The best estimate leans {lean} ({slope}), but the "
                    "uncertainty is too large to confirm your guess or the opposite one.")
    else:
        direction = "increase" if result.verdict == "significant increase" else "decrease"
        if expected.get(prediction) == result.verdict:
            text = "The data support your prediction."
        elif prediction == "No clear trend":
            text = f"The data show a likely {direction}."
        else:
            text = "The data point the other way."
        text += (f" The fitted trend is {slope}, and the uncertainty is small enough to call the {direction} "
                 "likely in this grid cell.")
    return text + " The window explorer below shows whether the answer changes when you pick other years."
