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

HELP = {
    "p": "How surprising a trend this large would be if there were no real trend, after allowing for "
         "month-to-month memory. Smaller means more surprising. It is not the chance that the trend is real.",
    "n_eff": "Neighbouring months tend to resemble each other, so they carry less independent information. "
             "This is roughly how many independent months the record is worth.",
    "coverage": "Share of months in the window that have data. Missing months are left out, never filled in.",
    "hac": "A second way to compute the p-value that handles month-to-month memory differently. "
           "It is shown as a cross-check and does not change the verdict.",
}


def _scale(result, unit: str) -> str | None:
    """Plain-language scale for the trend, built only from the engine's explainer numbers."""
    numbers = result.settings.get("explainer", {})
    raw, seasonal, fit = (numbers.get(k, {}) for k in ("raw", "seasonal", "fit"))
    values = [raw.get("mean"), seasonal.get("anomaly_sd"), fit.get("total_change"), fit.get("window_years")]
    if any(v is None or not math.isfinite(v) for v in values):
        return None
    mean, spread, total, years = values
    text = (f"To put this in scale: a typical month in this window averages {float(f'{mean:.2g}'):g} {unit}. "
            f"Even after the normal seasonal cycle is removed, a month usually differs from its usual value "
            f"by about {_amount(spread)} {unit}. The trend of {_signed(result.slope_per_decade)} {unit} per decade "
            f"adds up to a fitted total change of {_signed(total)} {unit} over the whole {years:g}-year window. ")
    if result.verdict == "not enough evidence":
        return text + ("Against month-to-month swings of this size, this record cannot tell that trend apart from "
                       "noise. Not significant does not mean no change: the true trend could be zero, or a real "
                       "change too small for this record to detect.")
    return text + ("Compared with those swings and the length of the record, the trend is large enough for the "
                   "model to call it likely. Likely is not proven: section 4 checks whether it survives other "
                   "reasonable choices.")


def _signed(value: float) -> str:
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return sign + _amount(value)


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
                    f"The best estimate is {_change(result.slope_per_decade, unit)} per decade")
        headline += (", but the data are also consistent with no change or a change in the other direction."
                     if result.ci[0] < 0 < result.ci[1] else ".")
    total = result.settings.get("explainer", {}).get("fit", {}).get("total_change")
    # Only a significant trend gets a total: an inconclusive fit should not read as a measured change.
    if result.verdict != "not enough evidence" and total is not None and math.isfinite(total):
        headline += f" The fitted change over the whole window is {_change(total, unit)}."
    st.subheader("2. How much did it change?")
    colour, icon = {
        "significant increase": ("#C2410C", "↑"),
        "significant decrease": ("#1D4ED8", "↓"),
    }.get(result.verdict, ("#64748B", "–"))
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
    scale = _scale(result, unit)
    if scale:
        st.write(scale)
    if variable == "GPM_PRECIP":
        last = bundle["full"].last_valid_index()
        if last is not None and plan.end[:7] > f"{last:%Y-%m}":
            st.caption(f"The precipitation record ends in {last:%B %Y}; later months in this window have no data.")
    with st.expander("For the statistically curious"):
        metrics = st.columns(4)
        metrics[0].metric("Primary p-value", f"{result.p:.3g}", help=HELP["p"])
        metrics[1].metric("Effective months (rough)", f"{result.n_eff:.0f} of {result.n}", help=HELP["n_eff"])
        metrics[2].metric("Monthly coverage", f"{result.coverage:.1%}", help=HELP["coverage"])
        metrics[3].metric("HAC cross-check p-value", f"{result.hac_p:.3g}", help=HELP["hac"])
        st.caption(f"Seasonal Sen slope: {result.sen_per_decade:.3f} {unit} per decade (descriptive cross-check).")
        if result.sen_per_decade == 0:
            st.caption("A Sen slope of exactly 0 is not an error. It is a median of year-to-year changes, and here "
                       "most of them are 0, for example because many months have the same value (dry-season months "
                       "with no rain).")
        st.markdown(VERDICT_RULE)
        for warning in result.warnings:
            st.caption(f"Note: {warning}")
