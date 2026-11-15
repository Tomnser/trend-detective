"""B2: capture a prediction and compare it with the unchanged engine verdict."""
from __future__ import annotations
import streamlit as st


def render(bundle: dict):
    if bundle.get("stage") == "choose":
        st.markdown("**Before you reveal the result, what do you expect?**")
        return st.radio("Your prediction", ["Rising", "Falling", "No clear trend"], index=None,
                        horizontal=True, key=f"prediction_{bundle['context']}")
    result, prediction = bundle.get("result"), bundle.get("prediction")
    if result is None:
        return
    if prediction is not None:
        expected = {"Rising": "significant increase", "Falling": "significant decrease"}
        if result.verdict == "not enough evidence":
            feedback = "Not enough evidence either way"
        elif expected.get(prediction) == result.verdict:
            feedback = "The data support your prediction"
        elif prediction == "No clear trend":
            direction = "increase" if result.verdict == "significant increase" else "decrease"
            feedback = f"The data show a likely {direction}"
        else:
            feedback = "The data point the other way"
        st.info(f"Your prediction: {prediction}. {feedback}.")
    st.caption("Not significant does not mean nothing is changing.")
