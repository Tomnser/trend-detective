"""E2: growing-season view. Shows an analysis.season_trend result; fits nothing itself."""
from __future__ import annotations

import calendar

import plotly.graph_objects as go
import streamlit as st

from catalogue import get_variable_meta

NEUTRAL, HIGHLIGHT, MEAN_LINE = "#94A3B8", "#C2410C", "#0F172A"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def season_unit(variable: str, how: str) -> str:
    """A summed season is a total: 'mm/month' becomes 'mm'. A mean keeps the variable's unit."""
    unit = get_variable_meta(variable)["display_unit"]
    return unit.removesuffix("/month") if how == "sum" else unit


def sentence(result, highlight_year: int | None) -> str:
    """The plain finding, built only from the engine result."""
    s = result.settings
    n = result.n
    name = "growing season" if s["months"] == [4, 5, 6, 7, 8, 9] else "season"
    first = ""
    if highlight_year in s["years"]:
        rank = s["rank_from_lowest"][s["years"].index(highlight_year)]
        place = "the driest" if rank == 1 else f"the {_ordinal(rank)} driest"
        first = f"{highlight_year} was {place} {name} of {n}. "
    p = "p < 0.01" if result.p < 0.01 else f"p = {result.p:.2f}"
    if result.verdict == "not enough evidence":
        return f"{first}An extreme year is not a trend: the {n} seasons show none ({p})."
    direction = "increase" if result.verdict == "significant increase" else "decrease"
    return f"{first}An extreme year is not a trend. Taken together, the {n} seasons show a likely {direction} ({p})."


def render(bundle: dict) -> None:
    plan, result = bundle["plan"], bundle["result"]
    if result is None or result.settings.get("mode") != "season":
        return
    s = result.settings
    variable = plan.variables[0]
    unit = season_unit(variable, s["how"])
    highlight = bundle.get("highlight_year", 2022)
    months = f"{calendar.month_name[s['months'][0]]}–{calendar.month_name[s['months'][-1]]}"
    kind = "total" if s["how"] == "sum" else "mean"

    st.subheader(f"One value per year: the {months} {kind}")
    st.markdown(f"**{sentence(result, highlight)}**")

    colours = [HIGHLIGHT if year == highlight else NEUTRAL for year in s["years"]]
    figure = go.Figure(go.Bar(x=s["years"], y=s["values"], marker_color=colours,
                              hovertemplate="%{x}: %{y:.0f} " + unit + "<extra></extra>"))
    figure.add_hline(y=s["mean"], line={"color": MEAN_LINE, "width": 1, "dash": "dot"},
                     annotation_text=f"mean {s['mean']:.0f} {unit}", annotation_position="top left")
    figure.update_layout(height=340, margin={"l": 10, "r": 10, "t": 30, "b": 10}, showlegend=False,
                         yaxis_title=f"{months} {kind} ({unit})", xaxis_title=None)
    st.plotly_chart(figure, width="stretch")
    st.caption(f"{get_variable_meta(variable)['label']}, one grid cell at {plan.place}. "
               f"Seasons used: {result.n}. The fitted change is {result.slope_per_decade:+.1f} {unit} per decade, "
               f"with a 95% interval from {result.ci[0]:+.1f} to {result.ci[1]:+.1f} {unit} per decade.")
    if s["years_skipped"]:
        st.caption("Left out because a season month is missing: " + ", ".join(map(str, s["years_skipped"])) + ".")

    with st.expander("For the statistically curious"):
        metrics = st.columns(3)
        metrics[0].metric("p-value", f"{result.p:.2g}")
        metrics[1].metric("Seasons used", f"{result.n}")
        metrics[2].metric("Sen's slope", f"{result.sen_per_decade:+.1f} {unit} per decade")
        st.write(f"Second check, Sen's slope: {result.sen_per_decade:+.1f} {unit} per decade (the median of all "
                 "year-to-year slopes; less sensitive to single extreme years).")
        st.write(f"Second check, leave one year out: the slope ranges from {s['leave_one_out_min']:+.1f} "
                 f"(without {s['leave_one_out_min_year']}) to {s['leave_one_out_max']:+.1f} "
                 f"(without {s['leave_one_out_max_year']}) {unit} per decade.")
        st.caption("Method: a straight line through the yearly values with the ordinary t-test. "
                   "Yearly values are treated as independent.")
        for warning in result.warnings:
            st.caption(f"Note: {warning}")
