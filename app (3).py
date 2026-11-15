from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from analysis import trend_analysis, validate_plan
from catalogue import DEFAULT_VARIABLES, LAST_YEAR, PLACES, get_variable_meta
from challenge import build_challenge_rows, regional_summary
from contracts import Plan
from data_access import load_full_series, load_plan_metadata, load_series_for_plan, places_sharing_cell
from panels.result import render as render_result
from panels.explorer import render as render_explorer
from panels.evidence import render as render_evidence
from processing import anomaly_series, climatology_for

# (button label, place, variable, start year, end year): examples fill in the form; they don't run it.
EXAMPLES = [
    ("Is Milan warming?", "Milan", "MERRA2_T2M", 1981, LAST_YEAR),
    ("Is the Po Valley getting drier?", "Po Valley", "GPM_PRECIP", 2001, LAST_YEAR),
    ("Was the Po Valley drying? (the view from 2022)", "Po Valley", "GPM_PRECIP", 2013, 2022),
]
PRESET_HINT = "Try a preset instead, for example the “Is Milan warming?” button above (Milan · temperature · 1981–2025)."


def theme_of(variable: str) -> str:
    return next(t for t, vs in DEFAULT_VARIABLES.items() if variable in vs)


def set_example(place: str, variable: str, start_year: int, end_year: int) -> None:
    meta = get_variable_meta(variable)
    st.session_state["place_choice"] = place
    st.session_state["theme_choice"] = theme_of(variable)
    st.session_state["variable_choice"] = variable
    st.session_state["start_choice"] = date(max(meta["first_year"], start_year), 1, 1)
    st.session_state["end_choice"] = date(end_year, 12, 1)


def decimal_year(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(index.year + (index.month - 1) / 12.0, index=index, dtype=float)


def trend_figure(series: pd.Series, anomalies: pd.Series, result, unit: str) -> go.Figure:
    """Raw values on top, anomalies + the engine's own trend and CI band below."""
    x = decimal_year(anomalies.index)
    clean = anomalies.notna()
    # OLS passes through (mean x, mean y) of the fitted points; draw the engine's slope, no refit.
    x_bar, y_bar = x[clean].mean(), anomalies[clean].mean()
    b, lo, hi = result.slope_per_decade / 10.0, result.ci[0] / 10.0, result.ci[1] / 10.0  # per year
    fitted = y_bar + b * (x - x_bar)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=(f"Monthly values ({unit})", f"Monthly anomalies ({unit})"))
    # NaN months are passed through (connectgaps=False), so lines break at gaps.
    fig.add_trace(go.Scatter(x=series.index, y=series, mode="lines", name="Monthly value",
                             line={"color": "#7f8c8d", "width": 1}, connectgaps=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=anomalies.index, y=y_bar + hi * (x - x_bar), mode="lines", line={"width": 0},
                             legendgroup="band", showlegend=False, hoverinfo="skip"), row=2, col=1)
    fig.add_trace(go.Scatter(x=anomalies.index, y=y_bar + lo * (x - x_bar), mode="lines", line={"width": 0},
                             fill="tonexty", fillcolor="rgba(31,119,180,0.18)", legendgroup="band",
                             name="Range of plausible trend slopes (95% CI)", hoverinfo="skip"), row=2, col=1)
    fig.add_trace(go.Scatter(x=anomalies.index, y=anomalies, mode="lines", name="Monthly anomaly",
                             line={"color": "#d35400", "width": 1}, connectgaps=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=anomalies.index, y=fitted, mode="lines", name="Trend",
                             line={"color": "#1f77b4", "width": 3}), row=2, col=1)
    fig.update_yaxes(title_text=f"Value ({unit})", row=1, col=1)
    fig.update_yaxes(title_text=f"Anomaly ({unit})", row=2, col=1)
    fig.update_xaxes(title_text="Month", row=2, col=1)
    fig.update_layout(height=640, hovermode="x unified", legend={"orientation": "h", "y": -0.12})
    return fig


def _num(value: float, fmt: str = "{:.3f}") -> str:
    """Table cell text; blank for values that are not computed (NaN)."""
    return fmt.format(value) if math.isfinite(value) else ""


def _jsonable(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def run_investigation(plan: Plan) -> dict:
    variable = plan.variables[0]
    series = load_series_for_plan(plan, variable)
    full_record = load_full_series(variable, plan.place, plan.lat, plan.lon)
    validation = validate_plan(plan, series)
    bundle = {"plan": plan, "series": series, "full": full_record, "validation": validation,
              "meta": load_plan_metadata(plan), "result": None, "challenges": [], "challenge_error": None,
              "shared_with": places_sharing_cell(variable, plan.place)}
    if validation.status != "supported":
        return bundle
    bundle["result"] = trend_analysis(plan, variable, series, reference_series=full_record)
    try:
        bundle["challenges"] = build_challenge_rows(plan, bundle["result"])
    except (RuntimeError, ValueError, OSError) as error:
        bundle["challenge_error"] = str(error)
    return bundle


def render_results(bundle: dict) -> None:
    plan, series, meta = bundle["plan"], bundle["series"], bundle["meta"]
    var = get_variable_meta(plan.variables[0])
    unit = var["display_unit"]
    req, cell = meta["requested_coordinates"], meta["resolved_cell_coordinates"]
    st.subheader(f"{plan.place} · {var['label']} · {plan.start[:7]} to {plan.end[:7]}")
    st.caption(var["definition"])
    st.caption(f"Requested point: {req['lat']:.2f}, {req['lon']:.2f} · Returned grid cell centre: "
               f"{cell['lat']}, {cell['lon']} (cell size {meta['grid_resolution']['lat']}° × {meta['grid_resolution']['lon']}°)")
    st.caption(f"Dataset: {meta['dataset']} · DOI: {meta['doi']} · retrieved {meta['retrieval_time']}"
               f" · {'from local cache' if meta['from_cache'] else 'downloaded now'}")
    for other in bundle.get("shared_with", []):
        st.warning(f"Same grid cell as {other}; not an independent result.")

    validation, result = bundle["validation"], bundle["result"]
    if result is None:
        st.error(f"{validation.status.title()}: {validation.reason}")
        st.info(validation.alternative)
        return

    render_result(bundle)
    render_evidence(bundle)

    anomalies = anomaly_series(series, climatology_for(bundle["full"]))
    st.plotly_chart(trend_figure(series, anomalies, result, unit), width="stretch")

    render_explorer(bundle)

    st.subheader("Challenge my finding")
    st.caption("A fixed set of date, nearby-cell, method and coverage checks. The baseline above stays visible; variants are not arbitrary user-selected searches.")
    if bundle["challenge_error"]:
        st.warning(f"Challenge checks unavailable: {bundle['challenge_error']}")
    rows = []
    for row in bundle["challenges"]:
        r = row.result
        if r is None:  # variant could not be computed; the note says why
            rows.append({"Check": row.check, "Variant": row.label, "Verdict": "unavailable", "What changes": row.note})
            continue
        rows.append({
            "Check": row.check,
            "Variant": row.label,
            f"Slope ({unit}/decade)": round(r.slope_per_decade, 3),
            "95% low": _num(r.ci[0]),
            "95% high": _num(r.ci[1]),
            "p": _num(r.p, "{:.3g}"),
            "HAC p": _num(r.hac_p, "{:.3g}"),
            "Coverage": f"{r.coverage:.1%}",
            "Verdict": r.verdict,
            "Passes threshold": ("yes" if r.settings.get("coverage_passes_variant") else "no") if row.check == "coverage" else "",
            "What changes": row.note,
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Regional check: " + regional_summary(bundle["challenges"], result))

    observations = pd.DataFrame({
        "date": series.index.strftime("%Y-%m-%d"), "value": series.to_numpy(), "anomaly": anomalies.to_numpy(),
        "units": unit, "variable": plan.variables[0], "cell_lat": cell["lat"], "cell_lon": cell["lon"],
    })
    evidence = _jsonable({
        "plan": asdict(plan), "provenance": meta, "result": asdict(result),
        "challenges": [{"check": c.check, "label": c.label, "note": c.note,
                        "result": asdict(c.result) if c.result is not None else None}
                       for c in bundle["challenges"]],
    })
    with st.expander("Values and source metadata"):
        st.dataframe(observations, hide_index=True)
        st.json(meta)
    left, right = st.columns(2)
    left.download_button("Download observations (CSV)", observations.to_csv(index=False).encode(),
                         "observations.csv", "text/csv", key="observations_download")
    right.download_button("Download evidence (JSON)", json.dumps(evidence, indent=2, ensure_ascii=False).encode(),
                          "trend_evidence.json", "application/json", key="evidence_download")


def main() -> None:
    st.set_page_config(page_title="Climate finding checker", page_icon="🌦️", layout="wide")
    st.title("Climate finding checker")
    st.caption("Explore whether a climate finding is sensitive to reasonable analytical choices. Results are not claims of certainty.")

    st.markdown("**Example questions**")
    for column, (label, place, variable, start_year, end_year) in zip(st.columns(len(EXAMPLES)), EXAMPLES):
        column.button(label, on_click=set_example, args=(place, variable, start_year, end_year), width="stretch")

    st.session_state.setdefault("place_choice", "Milan")
    st.session_state.setdefault("theme_choice", "temperature")
    st.subheader("Ask a structured question")
    # Theme and variable sit outside the form so the variable list follows the theme immediately.
    col1, col2 = st.columns(2)
    with col1:
        place = st.selectbox("Where?", list(PLACES), key="place_choice")
        theme = st.selectbox("Theme?", list(DEFAULT_VARIABLES), key="theme_choice")
        options = DEFAULT_VARIABLES[theme]
        if st.session_state.get("variable_choice") not in options:
            st.session_state["variable_choice"] = options[0]
        variable = st.selectbox("Variable", options, format_func=lambda key: get_variable_meta(key)["label"],
                                key="variable_choice")
    meta = get_variable_meta(variable)
    minimum, maximum = date(meta["first_year"], 1, 1), date(LAST_YEAR, 12, 1)
    for key, default in (("start_choice", minimum), ("end_choice", maximum)):
        st.session_state[key] = min(maximum, max(minimum, st.session_state.get(key, default)))
    with st.form("question_flow"):
        f1, f2 = st.columns(2)
        start = f1.date_input("Start date", min_value=minimum, max_value=maximum, key="start_choice")
        end = f2.date_input("End date", min_value=minimum, max_value=maximum, key="end_choice")
        st.caption(f"{meta['label']}: data available {meta['first_year']}–{LAST_YEAR}. "
                   "The supported analysis is a monthly trend for one selected variable and location.")
        submitted = st.form_submit_button("Check the finding", type="primary")

    if submitted:
        lat, lon = PLACES[place]
        plan = Plan(place=place, lat=lat, lon=lon, variables=[variable], start=start.isoformat(), end=end.isoformat())
        try:
            with st.spinner("Loading NASA data and analysing the record…"):
                st.session_state["applied"] = run_investigation(plan)
        except (RuntimeError, ValueError, OSError) as error:
            st.error(f"Could not load the data for {place} · {meta['label']}: {error}")
            st.info(PRESET_HINT)
            if "applied" in st.session_state:
                st.warning("The previous result is still shown below.")

    if "applied" in st.session_state:
        bundle = st.session_state["applied"]
        p = bundle["plan"]
        if (place, variable, start.isoformat()[:7], end.isoformat()[:7]) != (p.place, p.variables[0], p.start[:7], p.end[:7]):
            st.info("The inputs have changed. Press “Check the finding” to update the result below.")
        render_results(bundle)


main()
