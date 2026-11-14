from __future__ import annotations

from dataclasses import replace

import pandas as pd
from statsmodels.stats.multitest import multipletests

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


def _verdict(p: float, slope: float) -> str:
    if p < 0.05 and slope > 0:
        return "significant increase"
    if p < 0.05 and slope < 0:
        return "significant decrease"
    return "not enough evidence"


def _method_rows(plan: Plan, variable: str, full_record: pd.Series, baseline: TrendResult) -> list[ChallengeRow]:
    rows = [ChallengeRow("method", "Method: OLS (baseline)", baseline, "Primary result: OLS anomaly trend; uncertainty uses the stated rough AR(1) effective-sample-size adjustment.")]
    hac = trend_analysis(plan, variable, load_series_for_plan(plan, variable), reference_series=full_record, method="HAC cross-check")
    hac = replace(hac, ci=hac.hac_ci, p=hac.hac_p, verdict=_verdict(hac.hac_p, hac.slope_per_decade))
    rows.append(ChallengeRow("method", "Method: HAC/Newey–West", hac,
                             "Same OLS slope; 95% interval and p-value from the Newey–West (12-month Bartlett) standard error; verdict from the HAC p-value."))
    sen = baseline.sen_per_decade
    agrees = (sen > 0) == (baseline.slope_per_decade > 0) and sen != 0
    nan2 = (float("nan"), float("nan"))
    sen_result = replace(baseline, slope_per_decade=sen, ci=nan2, p=float("nan"), hac_p=float("nan"), hac_ci=nan2,
                         verdict="descriptive only",
                         settings={**baseline.settings, "method": "seasonal Sen cross-check", "sen_agrees_in_sign_with_ols": agrees})
    rows.append(ChallengeRow("method", f"Method: seasonal Sen’s slope ({'agrees' if agrees else 'DISAGREES'} in sign with OLS)", sen_result,
                             "Median within-calendar-month pairwise slope; descriptive only. No significance test: seasonal Mann–Kendall "
                             "gave 22% false positives on autocorrelated data in our null simulation."))
    return rows


WINDOW_GRID_COLUMNS = ["start", "end", "slope", "ci_low", "ci_high", "p", "verdict", "significant_bh"]


def window_grid(plan: Plan, variable: str) -> pd.DataFrame:
    """One engine fit for every date window of the full record with >= 10 complete years.

    A window runs from January of `start` to December of `end` (years); the last year may be
    partial. Only the plan's place and coordinates are used. Same engine and fixed full-record
    climatology as the baseline. `slope`, `ci_low`, `ci_high` are per decade, in display units.
    `significant_bh` is Benjamini-Hochberg at 0.05 over all windows; the windows overlap, so it
    is approximate.
    """
    full_record = load_full_series(variable, plan.place, plan.lat, plan.lon)
    first, last = full_record.index[0].year, full_record.index[-1].year
    rows = []
    for start in range(first, last + 1):
        for end in range(start, last + 1):
            variant = replace(plan, variables=[variable], start=f"{start}-01-01", end=f"{end}-12-01")
            data = load_series_for_plan(variant, variable)
            if coverage(data)["full_years"] < MIN_FULL_YEARS:
                continue
            r = trend_analysis(variant, variable, data, reference_series=full_record)
            rows.append((start, end, r.slope_per_decade, r.ci[0], r.ci[1], r.p, r.verdict))
    grid = pd.DataFrame(rows, columns=WINDOW_GRID_COLUMNS[:-1])
    grid["significant_bh"] = multipletests(grid["p"], alpha=0.05, method="fdr_bh")[0] if len(grid) else False
    return grid


def build_challenge_rows(plan: Plan, baseline: TrendResult) -> list[ChallengeRow]:
    variable = plan.variables[0]
    full_record = load_full_series(variable, plan.place, plan.lat, plan.lon)
    rows: list[ChallengeRow] = []
    rows += _date_rows(plan, variable, full_record)
    rows += _neighbour_rows(plan, variable, full_record)

    rows += _method_rows(plan, variable, full_record, baseline)

    data = load_series_for_plan(plan, variable)
    for label, threshold, month_threshold, note in (
        ("default threshold", 0.80, 0.70, "Requires >=10 complete years, >=80% of months and >=70% for each calendar month."),
        ("stricter threshold", 0.90, 0.75, "Requires >=10 complete years, >=90% of months and >=75% for each calendar month."),
    ):
        passes, _ = coverage_ok(data, threshold=threshold, month_threshold=month_threshold)
        threshold_result = TrendResult(**{**baseline.__dict__, "settings": {**baseline.settings, "coverage_threshold": threshold, "month_threshold": month_threshold, "coverage_passes_variant": passes}})
        rows.append(ChallengeRow("coverage", f"Coverage: {label}", threshold_result, note))
    return rows


def regional_summary(rows: list[ChallengeRow], baseline: TrendResult) -> str:
    """'k of N cells significant' over the baseline cell + computed neighbour cells.

    Only significance verdicts are counted: rows without a result and rows with the
    "descriptive only" verdict (no significance test) are excluded from k and N.
    """
    tested = [baseline] + [r.result for r in rows if r.check == "region" and r.result is not None]
    tested = [r for r in tested if r.verdict != "descriptive only"]
    k = sum(r.verdict.startswith("significant") for r in tested)
    return (f"{k} of {len(tested)} cells significant "
            "(cells are spatially correlated; counts are not independent confirmations)")
