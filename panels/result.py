"""B1: format the engine result without fitting or changing its verdict."""
from __future__ import annotations

import math
from html import escape
import streamlit as st
from catalogue import get_variable_meta

VERDICT_RULE = (
    "**How the verdict is decided:** by the adjusted-OLS p-value (OLS with an AR(1) "
    "effective-sample-size correction; 4% to 8% false positives in our simulations "
    "of 10 to 45 years; real series can be more complex). The HAC/Newey–West "
    "p-value is shown as a cross-check only and does not change the verdict."
)


def _amount(value: float) -> str:
    rounded = float(f"{abs(value):.2g}")
    return f"{rounded:g}"


def _change(value: float, unit: str) -> str:
    if value < 0:
        return f"a decrease of {_amount(value)} {unit}"
    if value > 0:
        return f"an increase of {_amount(value)} {unit}"
    return f"no change (0 {unit})"


def render(bundle: dict) -> None:
    plan, result = bundle["plan"], bundle["result"]
    if result is None:
        return  # The existing app handles validation errors before this panel.
    if bundle.get("section") == "limitations":
        st.subheader("5. What can we not conclude from the data?")
        st.write("This result describes one grid cell. It does not establish the pattern everywhere in the region. "
                 "A straight-line summary does not describe every year or predict future conditions. "
                 "These observations alone cannot identify a cause.")
        return
    variable = plan.variables[0]
    unit = get_variable_meta(variable)["display_unit"]
    subject = {
        "MERRA2_T2M": "This grid cell",
        "GPM_PRECIP": "Average monthly precipitation in this grid cell",
        "GLDAS_SSM": "Water stored in the top 10 cm of soil in this grid cell",
    }.get(variable, "The measured variable in this grid cell")
    up, down = ("warmed", "cooled") if variable == "MERRA2_T2M" else ("increased", "decreased")
    window = f"{plan.start[:4]} to {plan.end[:4]}"
    if result.verdict == "significant increase":
        headline = f"{subject} likely {up} by about {_amount(result.slope_per_decade)} {unit} per decade from {window}."
    elif result.verdict == "significant decrease":
        headline = f"{subject} likely {down} by about {_amount(result.slope_per_decade)} {unit} per decade from {window}."
    else:
        headline = (f"The evidence does not establish a clear trend in this grid cell from {window}. "
                    f"The fitted estimate is {_change(result.slope_per_decade, unit)} per decade.")
    total = result.settings.get("explainer", {}).get("fit", {}).get("total_change")
    # Only a significant trend gets a total: an inconclusive fit should not read as a measured change.
    if result.verdict != "not enough evidence" and total is not None and math.isfinite(total):
        headline += f" The fitted change over the whole window is {_change(total, unit)}."
    st.subheader("2. How much did it change?")
    colour, icon = {
        "significant increase": ("#C2410C", "↑"),
        "significant decrease": ("#1D4ED8", "↓"),
    }.get(result.verdict, ("#64748B", "?"))
    st.markdown(
        f"<div style='border-left:5px solid {colour};padding:18px 20px;"
        f"background:#FFFFFF;border-radius:8px;'>"
        f"<p style='font-size:1.3rem;line-height:1.5;margin:0;color:#0F172A;'>"
        f"<span style='color:{colour};font-weight:700;'>{icon}</span> {escape(headline)}</p></div>",
        unsafe_allow_html=True,
    )
    st.subheader("3. How strong is the statistical evidence?")
    st.write(f"The model's 95% interval runs from {_change(result.ci[0], unit)} "
             f"to {_change(result.ci[1], unit)} per decade.")
    if result.verdict == "not enough evidence":
        st.caption("A result without a clear direction does not mean nothing is changing.")
    if variable == "GPM_PRECIP":
        last = bundle["full"].last_valid_index()
        if last is not None and plan.end[:7] > f"{last:%Y-%m}":
            st.caption(f"The precipitation record ends in {last:%B %Y}; later months in this window have no data.")
    with st.expander("For the statistically curious"):
        metrics = st.columns(4)
        metrics[0].metric("Primary p-value", f"{result.p:.3g}")
        metrics[1].metric("Effective months (rough)", f"{result.n_eff:.0f} of {result.n}")
        metrics[2].metric("Monthly coverage", f"{result.coverage:.1%}")
        metrics[3].metric("HAC cross-check p-value", f"{result.hac_p:.3g}")
        st.caption(f"Seasonal Sen slope: {result.sen_per_decade:.3f} {unit} per decade (descriptive cross-check).")
        st.markdown(VERDICT_RULE)
        for warning in result.warnings:
            st.caption(f"Note: {warning}")
