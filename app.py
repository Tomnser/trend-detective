from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from analysis import season_trend, trend_analysis, validate_plan
from catalogue import DEFAULT_VARIABLES, LAST_YEAR, PLACES, get_variable_meta
from challenge import build_challenge_rows, regional_summary, robustness_counts
from contracts import Plan
from data_access import load_full_series, load_plan_metadata, load_series_for_plan, places_sharing_cell
from panels.result import render as render_result, render_details
from panels.explorer import render as render_explorer
from panels.evidence import render as render_evidence
from panels.explainer import render as render_explainer
from panels.prediction import render as render_prediction
from panels.home import render as render_home
from panels.season import render as render_season
from processing import anomaly_series, climatology_for

# (button label, place, variable, start year, end year): examples fill in the form; they don't run it.
EXAMPLES = [
    ("How much has Milan warmed?", "Milan", "MERRA2_T2M", 1981, LAST_YEAR),
    ("Is the Po Valley getting drier?", "Po Valley", "GPM_PRECIP", 2001, LAST_YEAR),
    ("Was the Po Valley drying? (the view from 2022)", "Po Valley", "GPM_PRECIP", 2013, 2022),
    ("How has temperature changed near Seville?", "Seville", "MERRA2_T2M", 1981, LAST_YEAR),
    ("How has rainfall changed near Niamey?", "Niamey", "GPM_PRECIP", 2001, LAST_YEAR),
    ("How has temperature changed near Fairbanks?", "Fairbanks", "MERRA2_T2M", 1981, LAST_YEAR),
    ("How has surface soil water changed in Sierra Nevada?", "Sierra Nevada", "GLDAS_SSM", 2001, LAST_YEAR),
    ("How has rainfall changed at the Murray–Darling Basin point?", "Murray–Darling Basin", "GPM_PRECIP", 2001, LAST_YEAR),
]
# Growing-season view (April–September, one value per year): only where that season applies.
SEASON_PLACES = ("Po Valley", "Milan")
SEASON_HOW = {"GPM_PRECIP": "sum", "GLDAS_SSM": "mean"}
SEASON_MONTHS = [4, 5, 6, 7, 8, 9]
PRESET_HINT = "Choose an investigation above, for example “How much has Milan warmed?”."


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
    trend_colour = {"significant increase": "#C2410C", "significant decrease": "#1D4ED8"}.get(result.verdict, "#64748B")

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
                             line={"color": trend_colour, "width": 3}), row=2, col=1)
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


def _provenance(var: dict, meta: dict) -> None:
    """Cell centre, dataset, DOI and retrieval date stay visible on every result."""
    req, cell = meta["requested_coordinates"], meta["resolved_cell_coordinates"]
    st.caption(var["definition"])
    st.caption(f"Requested point: {req['lat']:.2f}, {req['lon']:.2f} · Returned grid cell centre: "
               f"{cell['lat']}, {cell['lon']} (cell size {meta['grid_resolution']['lat']}° × {meta['grid_resolution']['lon']}°)")
    st.caption(f"Dataset: {meta['dataset']} · DOI: {meta['doi']} · retrieved {meta['retrieval_time']}"
               f" · {'from local cache' if meta['from_cache'] else 'downloaded now'}")


def render_results(bundle: dict) -> None:
    plan, series, meta = bundle["plan"], bundle["series"], bundle["meta"]
    var = get_variable_meta(plan.variables[0])
    unit = var["display_unit"]
    cell = meta["resolved_cell_coordinates"]
    st.subheader("Your result")
    st.markdown(f"**{plan.place} · {var['label']} · {plan.start[:7]} to {plan.end[:7]}**")
    for other in bundle.get("shared_with", []):
        st.warning(f"Same grid cell as {other}; not an independent result.")

    validation, result = bundle["validation"], bundle["result"]
    if result is None:
        _provenance(var, meta)
        st.error(f"{validation.status.title()}: {validation.reason}")
        st.info(validation.alternative)
        return

    render_result(bundle)
    render_prediction(bundle)
    _provenance(var, meta)

    st.subheader("But can you trust this conclusion?")
    st.write("A trend line depends on which years you pick. Below, the same engine is run on every window "
             "of ten or more complete years in this record.")
    render_explorer(bundle)

    st.subheader("The evidence in detail")
    render_details(bundle)
    render_evidence(bundle)

    anomalies = anomaly_series(series, climatology_for(bundle["full"]))
    st.plotly_chart(trend_figure(series, anomalies, result, unit), width="stretch")
    st.caption("Top: the monthly values as measured. Bottom: the same months with the normal seasonal cycle "
               "removed (anomalies), the fitted trend (dark line) and the range of plausible trends "
               "(shaded band, 95% interval).")

    variable = plan.variables[0]
    if plan.place in SEASON_PLACES and variable in SEASON_HOW:
        try:
            season = season_trend(bundle["full"], SEASON_MONTHS, SEASON_HOW[variable])
            render_season({"plan": plan, "result": season})
        except (RuntimeError, ValueError) as error:
            st.caption(f"Growing-season view unavailable: {error}")

    render_explainer(bundle)

    st.markdown("**Fixed checks: other date windows, nearby cells, other methods**")
    if bundle["challenge_error"]:
        st.warning(f"Challenge checks unavailable: {bundle['challenge_error']}")
    if bundle["challenges"]:
        st.write(robustness_counts(bundle["challenges"], result)["sentence"])
    rows = []
    for row in bundle["challenges"]:
        r = row.result
        if r is None:  # variant could not be computed; the note says why
            rows.append({"Check": row.check, "Variant": row.label, "Verdict": "unavailable", "What changes": row.note})
            continue
        rows.append({
            "Check": row.check,
            "Variant": row.label,
            f"Slope ({unit} per decade)": round(r.slope_per_decade, 3),
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
        with st.expander("Show every check"):
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("Regional check: " + regional_summary(bundle["challenges"], result))

    render_result({**bundle, "section": "limitations"})

    observations = pd.DataFrame({
        "date": series.index.strftime("%Y-%m-%d"), "value": series.to_numpy(), "anomaly": anomalies.to_numpy(),
        "units": unit, "variable": plan.variables[0], "cell_lat": cell["lat"], "cell_lon": cell["lon"],
    })
    evidence = _jsonable({
        "plan": asdict(plan), "provenance": meta, "result": asdict(result),
        "prediction": bundle.get("prediction"),
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
    st.set_page_config(page_title="Trend Detective", page_icon="🌦️", layout="wide")
    render_home({"examples": EXAMPLES, "on_select": set_example})

    st.session_state.setdefault("place_choice", "Milan")
    st.session_state.setdefault("theme_choice", "temperature")
    with st.expander("Build your own", expanded=False):
        # These selectors stay outside the form so their dependent options update immediately.
        left, right = st.columns(2)
        with left:
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
        with right:
            start = st.date_input("Start date", min_value=minimum, max_value=maximum, key="start_choice")
            end = st.date_input("End date", min_value=minimum, max_value=maximum, key="end_choice")
    with st.form("question_flow"):
        st.caption(f"Selected: {place} · {meta['label']} · {start:%Y-%m} to {end:%Y-%m}. "
                   "Results describe one sampled grid cell.")
        prediction = render_prediction({"stage": "choose", "context": f"{place}_{variable}_{start}_{end}"})
        submitted = st.form_submit_button("Check the finding", type="primary")

    if submitted:
        lat, lon = PLACES[place]
        plan = Plan(place=place, lat=lat, lon=lon, variables=[variable], start=start.isoformat(), end=end.isoformat())
        try:
            with st.spinner("Loading NASA data and analysing the record…"):
                candidate = run_investigation(plan)
                candidate["prediction"] = prediction
                st.session_state["applied"] = candidate
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
