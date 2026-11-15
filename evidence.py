"""B3: display the engine's model-dependent evidence estimates unchanged."""
from __future__ import annotations

import math
import streamlit as st
from catalogue import get_variable_meta


def _number(value: float) -> str:
    return f"{float(f'{value:.2g}'):g}"


def render(bundle: dict) -> None:
    result = bundle["result"]
    if result is None or result.verdict != "not enough evidence":
        return
    evidence = result.settings.get("evidence", {})
    years = evidence.get("record_years")
    threshold = evidence.get("smallest_detectable_trend_per_decade")
    if any(value is None or not math.isfinite(value) or value <= 0 for value in (years, threshold)):
        st.caption("A model-dependent detection estimate is unavailable for this record.")
        return
    unit = get_variable_meta(bundle["plan"].variables[0])["display_unit"]
    st.markdown("**How much change could this record detect?**")
    st.write(f"Under the model's assumptions, this {_number(years)}-year record would reliably "
             f"detect a change of about {_number(threshold)} {unit} per decade or more. "
             f"The estimated rate here is {result.slope_per_decade:+.2g} {unit} per decade.")
    if abs(result.slope_per_decade) < threshold:
        st.write("A change that small cannot yet be clearly distinguished from noise under this model.")
    else:
        st.write("This rough detection threshold does not replace the uncertainty test; "
                 "the result above remains inconclusive.")
    needed = evidence.get("years_needed_under_cap")
    if needed is not None and math.isfinite(needed) and 0 < needed < 100:
        st.write(f"At the estimated rate, a record of about {needed:.0f} years in total would be needed. "
                 "This is a rough, model-dependent figure.")
    st.caption("These estimates depend on the model's rate, variability and month-to-month memory assumptions. "
               "They are not a forecast or a promise that more years will settle the question.")
