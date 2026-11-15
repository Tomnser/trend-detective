"""C2/C3: cached window lookup and sensitivity display; no model fitting here."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from catalogue import get_variable_meta
from challenge import window_grid
from contracts import Plan


@st.cache_data(show_spinner="Preparing the window explorer…", max_entries=32)
def _grid(place: str, lat: float, lon: float, variable: str,
          record_start: str, record_end: str) -> pd.DataFrame:
    plan = Plan(place, lat, lon, [variable], record_start, record_end)
    return window_grid(plan, variable)


def _examples(grid: pd.DataFrame, plan: Plan, result, lower_word: str, higher_word: str) -> str:
    """Name real windows from the grid that look significant, and compare them with the chosen window."""
    span = lambda rows: ", ".join(f"{int(r.start)}–{int(r.end)}" for r in rows.itertuples())  # noqa: E731
    parts = []
    for verdict, word in (("significant decrease", lower_word), ("significant increase", higher_word)):
        chosen = (grid["start"] == int(plan.start[:4])) & (grid["end"] == int(plan.end[:4]))
        rows = grid.loc[(grid["verdict"] == verdict) & ~chosen].assign(length=lambda d: d["end"] - d["start"])
        rows = rows.sort_values(["length", "start"], ascending=[False, True]).head(3)
        if not rows.empty:
            parts.append(f"Other windows that look significantly {word} include {span(rows)}.")
    any_significant = bool(parts)
    if not any_significant and grid["verdict"].str.startswith("significant").any():
        parts.append("No other window looks significant.")
    elif not any_significant:
        parts.append("No window of ten or more complete years looks significant here, "
                     "so no choice of years gives a confident claim in either direction.")
    same = int((grid["verdict"] == result.verdict).sum())
    parts.append(f"Your chosen window, {plan.start[:4]}–{plan.end[:4]}, gives: {result.verdict}. "
                 f"{same} of {len(grid)} windows give the same verdict.")
    if any_significant and result.verdict == "not enough evidence":
        parts.append("Someone who reported only one of the significant windows could make a confident claim "
                     "that your window does not support.")
    return " ".join(parts)


@st.fragment
def render(bundle: dict) -> None:
    plan, full = bundle["plan"], bundle["full"]
    variable = plan.variables[0]
    unit = get_variable_meta(variable)["display_unit"]
    try:
        grid = _grid(plan.place, plan.lat, plan.lon, variable,
                     str(full.index.min().date()), str(full.index.max().date()))
    except (RuntimeError, ValueError, OSError) as error:
        st.warning(f"Window explorer unavailable: {error}")
        return
    if grid.empty:
        st.info("No windows meet the engine's requirement of ten complete years.")
        return

    down = int((grid["verdict"] == "significant decrease").sum())
    up = int((grid["verdict"] == "significant increase").sum())
    lower_word, higher_word = ("drier", "wetter") if variable in ("GPM_PRECIP", "GLDAS_SSM") else ("cooler", "warmer")
    st.write(f"Of {len(grid)} possible windows, {down + up} look significant: "
             f"{down} {'says' if down == 1 else 'say'} {lower_word} and {up} {'says' if up == 1 else 'say'} {higher_word}.")
    st.write(_examples(grid, plan, bundle["result"], lower_word, higher_word))
    st.caption("These windows overlap, so they are not independent tests. "
               "The lesson is that the conclusion depends on the window.")
    st.caption("The baseline above stays fixed. Move the handles to inspect another window.")
    first, last = int(grid["start"].min()), int(grid["end"].max())
    initial = (max(first, min(last, int(plan.start[:4]))),
               max(first, min(last, int(plan.end[:4]))))
    start, end = st.slider("Explore start and end years", min_value=first, max_value=last,
                           value=initial, step=1,
                           key=f"window_{plan.place}_{plan.lat}_{plan.lon}_{variable}_{plan.start}_{plan.end}")
    selected = grid.loc[(grid["start"] == start) & (grid["end"] == end)]
    left, right = st.columns(2)
    with left:
        if selected.empty:
            st.info("This window has fewer than ten complete years or is absent from the engine grid. "
                    "Choose a longer window; no result has been invented.")
        else:
            row = selected.iloc[0]
            st.markdown(f"**Selected window: {start}–{end}**")
            st.metric(f"Change ({unit} per decade)", f"{row['slope']:+.3f}")
            st.write(f"Range of plausible trends (95% interval): {row['ci_low']:+.3f} to {row['ci_high']:+.3f} {unit} per decade.")
            st.write(f"Engine verdict: **{row['verdict']}**.")
            values = full.loc[f"{start}-01-01":f"{end}-12-31"]
            figure = go.Figure(go.Scatter(x=values.index, y=values, mode="lines",
                                          name="Monthly value", connectgaps=False,
                                          line={"color": "#64748b", "width": 1}))
            figure.update_layout(height=280, margin=dict(l=10, r=10, t=20, b=10),
                                 xaxis_title="Month", yaxis_title=unit)
            st.plotly_chart(figure, width="stretch")
            st.caption("Chart: original monthly values. Trend and interval: the engine's season-adjusted result.")
            if end == full.index.max().year and full.index.max().month < 12:
                st.caption(f"The last available observation is {full.index.max():%Y-%m}; "
                           "the final calendar year is incomplete.")

    # Display categories use the engine verdict; no p-value or correction is recomputed.
    display = grid.copy()
    display["colour"] = display["slope"].map(lambda slope: 1 if slope > 0 else -1 if slope < 0 else 0)
    display.loc[display["verdict"] == "significant decrease", "colour"] = -2
    display.loc[display["verdict"] == "significant increase", "colour"] = 2
    matrix = display.pivot(index="start", columns="end", values="colour")
    fields = [display.pivot(index="start", columns="end", values=field)
              for field in ("slope", "ci_low", "ci_high")]
    heatmap = go.Figure(go.Heatmap(
        x=matrix.columns, y=matrix.index, z=matrix.to_numpy(), zmin=-2, zmax=2,
        colorscale=[[0, "#1d4ed8"], [.125, "#1d4ed8"], [.125, "#bfdbfe"], [.375, "#bfdbfe"],
                    [.375, "#e2e8f0"], [.625, "#e2e8f0"], [.625, "#fed7aa"], [.875, "#fed7aa"],
                    [.875, "#c2410c"], [1, "#c2410c"]],
        customdata=np.stack([field.to_numpy() for field in fields], axis=-1),
        hoverongaps=False,
        hovertemplate=("Start %{y}; end %{x}<br>Trend %{customdata[0]:+.3f} " + unit + " per decade"
                       "<br>95% interval [%{customdata[1]:+.3f}, %{customdata[2]:+.3f}]<extra></extra>"),
        colorbar=dict(tickvals=[-2, -1, 0, 1, 2],
                      ticktext=["Significant decrease", "Decrease, not significant", "Zero slope",
                                "Increase, not significant", "Significant increase"])))
    heatmap.add_trace(go.Scatter(x=[end], y=[start], mode="markers", showlegend=False,
                                 marker=dict(symbol="square-open", size=16, color="#0f172a", line=dict(width=2)),
                                 hoverinfo="skip"))
    heatmap.update_layout(height=430, xaxis_title="End year", yaxis_title="Start year",
                          margin=dict(l=10, r=10, t=20, b=10))
    with right:
        st.plotly_chart(heatmap, width="stretch")
        st.caption("Blue = decreasing; orange = increasing. Dark cells are a statistically significant "
                   "trend under the engine's test. Pale cells are not. Empty cells have no eligible window. "
                   "The outlined square marks your selection.")
