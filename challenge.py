from __future__ import annotations

import pandas as pd

from analysis import trend_analysis
from catalogue import get_variable_meta
from contracts import ChallengeRow, Plan, TrendResult
from data_access import load_full_series, load_series_for_plan
from processing import coverage, coverage_ok

NEIGHBOUR_OFFSET_DEG = 0.5  # ~50 km
DATE_START_YEARS = (1991, 2001, 2011, 2016)  # plus the variable's first_year
MIN_FULL_YEARS = 10


def _copy_plan(plan: Plan, *, start: str | None = None, lat: float | None = None, lon: float | None = None) -> Plan:
    return Plan(
        place=plan.place,
        lat=plan.lat if lat is None else lat,
        lon=plan.lon if lon is None else lon,
        variables=list(plan.variables),
        start=start or plan.start,
        end=plan.end,
        kind=plan.kind,
        mode=plan.mode,
        season=plan.season,
        lat2=plan.lat2,
        lon2=plan.lon2,
    )


def grid_step(resolution: float, offset: float = NEIGHBOUR_OFFSET_DEG) -> float:
    """Offset snapped to a whole number of grid cells (at least one)."""
    return max(1, round(offset / resolution)) * resolution


def date_start_years(first_year: int) -> list[int]:
    return sorted({max(first_year, y) for y in (first_year, *DATE_START_YEARS)})


def _date_rows(plan: Plan, variable: str, full_record: pd.Series) -> list[ChallengeRow]:
    rows = []
    end = pd.Timestamp(plan.end)
    for year in date_start_years(get_variable_meta(variable)["first_year"]):
        start = f"{year}-01-01"
        if pd.Timestamp(start) >= end:
            continue
        variant = _copy_plan(plan, start=start)
        data = load_series_for_plan(variant, variable)
        if coverage(data)["full_years"] < MIN_FULL_YEARS:
            continue  # too short for a trend (needs >= 10 complete years)
        result = trend_analysis(variant, variable, data, reference_series=full_record)
        rows.append(ChallengeRow("date", f"Date: {start[:7]} to {plan.end[:7]}", result,
                                 "Changes only the fitted date window; the full-record monthly climatology stays fixed."))
    return rows


def _neighbour_rows(plan: Plan, variable: str, full_record: pd.Series) -> list[ChallengeRow]:
    a = full_record.attrs
    lat0, lon0, dlat, dlon = a.get("cell_lat"), a.get("cell_lon"), a.get("lat_res"), a.get("lon_res")
    if None in (lat0, lon0, dlat, dlon):
        return [ChallengeRow("region", "Region: neighbours", None,
                             "Unavailable: the source did not report the cell centre and grid size.")]
    step_lat, step_lon = grid_step(dlat), grid_step(dlon)
    seen = {(round(lat0, 4), round(lon0, 4))}
    rows = []
    for direction, sign_lat, sign_lon in (("north", 1, 0), ("south", -1, 0), ("east", 0, 1), ("west", 0, -1)):
        # Request the centre of the cell `step` away from the RETURNED baseline cell.
        target_lat = round(lat0 + sign_lat * step_lat, 4)
        target_lon = round(lon0 + sign_lon * step_lon, 4)
        variant = _copy_plan(plan, lat=target_lat, lon=target_lon)
        label = f"Region: {direction} neighbour"
        try:
            reference = load_full_series(variable, variant.place, target_lat, target_lon)
            cell = (round(reference.attrs["cell_lat"], 4), round(reference.attrs["cell_lon"], 4))
            label += f" (cell {cell[0]}, {cell[1]})"
            if cell in seen:
                raise ValueError("the source returned a cell that was already checked")
            seen.add(cell)
            data = load_series_for_plan(variant, variable)
            ok, cov = coverage_ok(data)
            if not ok:
                raise ValueError(f"coverage too low ({cov['full_years']} complete years, {cov['frac_present']:.0%} of months)")
            result = trend_analysis(variant, variable, data, reference_series=reference)
        except (RuntimeError, ValueError, OSError) as error:
            rows.append(ChallengeRow("region", label, None, f"Unavailable: {error}"))
            continue
        rows.append(ChallengeRow("region", label, result,
                                 f"A separate grid cell {step_lat:g}° lat / {step_lon:g}° lon away; uses its own full-record climatology."))
    return rows


def build_challenge_rows(plan: Plan, baseline: TrendResult) -> list[ChallengeRow]:
    variable = plan.variables[0]
    full_record = load_full_series(variable, plan.place, plan.lat, plan.lon)
    rows: list[ChallengeRow] = []
    rows += _date_rows(plan, variable, full_record)
    rows += _neighbour_rows(plan, variable, full_record)

    rows.append(ChallengeRow("method", "Method: OLS (baseline)", baseline, "Primary result: OLS anomaly trend; uncertainty uses the stated rough AR(1) effective-sample-size adjustment."))
    hac_result = trend_analysis(plan, variable, load_series_for_plan(plan, variable), reference_series=full_record, method="HAC cross-check")
    rows.append(ChallengeRow("method", "Method: HAC/Newey–West", hac_result, "Keeps the OLS slope; compare the fixed 12-month HAC p-value in the result settings and cross-check."))
    sen_result = trend_analysis(plan, variable, load_series_for_plan(plan, variable), reference_series=full_record, method="seasonal Sen cross-check")
    sen_result.settings["cross_check_sen_slope_per_decade"] = sen_result.sen_per_decade
    rows.append(ChallengeRow("method", "Method: seasonal Sen’s slope", sen_result, "Reports the median within-calendar-month pairwise slope as a robust slope cross-check; it does not replace the primary verdict."))

    data = load_series_for_plan(plan, variable)
    for label, threshold, month_threshold, note in (
        ("default threshold", 0.80, 0.70, "Requires >=10 complete years, >=80% of months and >=70% for each calendar month."),
        ("stricter threshold", 0.90, 0.75, "Requires >=10 complete years, >=90% of months and >=75% for each calendar month."),
    ):
        passes, _ = coverage_ok(data, threshold=threshold, month_threshold=month_threshold)
        threshold_result = TrendResult(**{**baseline.__dict__, "settings": {**baseline.settings, "coverage_threshold": threshold, "month_threshold": month_threshold, "coverage_passes_variant": passes}})
        rows.append(ChallengeRow("coverage", f"Coverage: {label}", threshold_result, note))
    return rows
