"""C4: explain the engine's four steps without fitting another model."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from catalogue import get_variable_meta
from processing import anomaly_series


def _line(series: pd.Series, unit: str, name: str) -> go.Figure:
    figure = go.Figure(go.Scatter(x=series.index, y=series, mode="lines", name=name,
                                  connectgaps=False, line={"color": "#64748b", "width": 1}))
    figure.update_layout(height=190, margin=dict(l=10, r=10, t=15, b=10),
                         xaxis_title="Month", yaxis_title=unit, showlegend=False)
    return figure


@st.fragment
def render(bundle: dict) -> None:
    result = bundle["result"]
    if result is None:
        return
    numbers = result.settings.get("explainer", {})
    if not all(step in numbers for step in ("raw", "seasonal", "fit", "uncertainty")):
        st.info("The engine did not supply the numbers for the explainer.")
        return
    raw, seasonal, fit, uncertainty = (numbers[step] for step in ("raw", "seasonal", "fit", "uncertainty"))
    plan, series = bundle["plan"], bundle["series"]
    unit = get_variable_meta(plan.variables[0])["display_unit"]
    # Use the full-record calendar-month means supplied by the engine, unchanged.
    climatology = pd.Series(seasonal["climatology"], index=range(1, 13), dtype=float)
    anomalies = anomaly_series(series, climatology)
    with st.expander("How we got this"):
        st.markdown("**1. Start with the monthly data**")
        last = series.last_valid_index()
        after_end = int((series.index > last).sum()) if last is not None else 0
        missing = f"{raw['months_missing']} missing"
        if after_end and after_end == raw["months_missing"]:
            missing += f": the record ends {last:%Y-%m}"
        elif after_end:
            missing += f", {after_end} of them after the record ends {last:%Y-%m}"
        st.write(f"The window {raw['first_month']} to {raw['last_month']} contains {raw['months']} months "
                 f"({missing}), with observed values from {raw['min']:.2f} to "
                 f"{raw['max']:.2f} {unit} and a mean of {raw['mean']:.2f} {unit}.")
        st.plotly_chart(_line(series, unit, "Monthly values"), width="stretch")

        st.markdown("**2. Remove the repeating seasonal cycle**")
        st.write(f"We subtract the calendar-month cycle from the whole record "
                 f"({seasonal['climatology_first_month']} to {seasonal['climatology_last_month']}, "
                 f"seasonal range {seasonal['seasonal_range']:.2f} {unit}), changing the standard deviation "
                 f"from {raw['sd']:.2f} to {seasonal['anomaly_sd']:.2f} {unit}.")
        view = st.radio("Seasonal adjustment view", ["Raw", "Deseasonalised"], index=1, horizontal=True,
                        key=f"explainer_view_{plan.place}_{plan.variables[0]}_{plan.start}_{plan.end}")
        shown = series if view == "Raw" else anomalies
        st.plotly_chart(_line(shown, unit, view), width="stretch")

        st.markdown("**3. Fit the long-term trend**")
        st.write(f"The engine fits {fit['slope_per_decade']:+.3f} {unit} per decade across "
                 f"{fit['window_years']:g} years, a fitted total change of {fit['total_change']:+.2f} {unit}.")
        # Plot the already-fitted parameters; do not call polyfit or an engine refit.
        origin = anomalies.first_valid_index()
        elapsed = ((anomalies.index.year - origin.year) * 12 + anomalies.index.month - origin.month) / 12.0
        fitted = pd.Series(fit["anomaly_at_start"] + fit["slope_per_year"] * elapsed,
                           index=anomalies.index).where(anomalies.notna())
        figure = _line(anomalies, unit, "Monthly anomaly")
        figure.add_trace(go.Scatter(x=fitted.index, y=fitted, mode="lines", name="Engine trend",
                                    connectgaps=False, line={"color": "#1f77b4", "width": 3}))
        figure.update_layout(showlegend=True)
        st.plotly_chart(figure, width="stretch")

        st.markdown("**4. Account for month-to-month memory**")
        st.write(f"The adjustment gives about {uncertainty['effective_months']:.0f} effective months "
                 f"from {uncertainty['months_used']} observed months and changes the standard error from "
                 f"{uncertainty['naive_se_per_decade']:.3f} to {uncertainty['adjusted_se_per_decade']:.3f} "
                 f"{unit} per decade, with a 95% interval of {uncertainty['ci_low']:+.3f} to "
                 f"{uncertainty['ci_high']:+.3f} {unit} per decade.")
        figure = go.Figure(go.Bar(x=["Before adjustment", "After adjustment"],
                                  y=[uncertainty["naive_se_per_decade"], uncertainty["adjusted_se_per_decade"]],
                                  marker_color=["#94a3b8", "#1f77b4"]))
        figure.update_layout(height=190, margin=dict(l=10, r=10, t=15, b=10),
                             yaxis_title="Standard error")
        st.plotly_chart(figure, width="stretch")
        st.caption(f"Standard error of the trend, in {unit} per decade.")
