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


def build_challenge_rows(plan: Plan, baseline: TrendResult, neighbours: bool = True) -> list[ChallengeRow]:
    """All challenge rows. `neighbours=False` skips the 4 nearby cells (4 downloads for a new point)."""
    variable = plan.variables[0]
    full_record = load_full_series(variable, plan.place, plan.lat, plan.lon)
    rows: list[ChallengeRow] = []
    rows += _date_rows(plan, variable, full_record)
    if neighbours:
        rows += _neighbour_rows(plan, variable, full_record)
    rows += _method_rows(plan, variable, full_record, baseline)

    return rows


def robustness_counts(rows: list[ChallengeRow], baseline: TrendResult) -> dict:
    """Real counts for the robustness sentence: how many date windows and nearby cells agree with the baseline.

    Only computed rows count (rows without a result are left out of the totals). "Same direction"
    means the slope has the baseline's sign; "significant" means significant in that direction.
    `sentence` is ready to show; the cells part is omitted when no nearby cell is loaded.
    """
    sign = (baseline.slope_per_decade > 0) - (baseline.slope_per_decade < 0)
    wanted = {1: "significant increase", -1: "significant decrease"}.get(sign)
    counts = {"baseline_significant": baseline.verdict.startswith("significant")}
    for key, check in (("windows", "date"), ("cells", "region")):
        results = [r.result for r in rows if r.check == check and r.result is not None]
        counts[f"{key}_total"] = len(results)
        counts[f"{key}_same_direction"] = sum(sign != 0 and r.slope_per_decade * sign > 0 for r in results)
        counts[f"{key}_significant"] = sum(r.verdict == wanted for r in results)
    # Start years the date check tries; those with fewer than 10 complete years are skipped as too short.
    meta, end = get_variable_meta(baseline.settings.get("variable", "")), baseline.settings.get("end")
    tried = len([y for y in date_start_years(meta["first_year"]) if f"{y}-01-01" < end]) if meta and end else counts["windows_total"]
    counts["windows_tried"] = tried
    w, c = counts["windows_total"], counts["cells_total"]
    short = f" ({tried} tried; {tried - w} too short)" if tried > w else ""
    cells = lambda k: f" and {counts[k]} of {c} nearby cells" if c else ""  # noqa: E731
    counts["sentence"] = (
        f"The direction holds in {counts['windows_same_direction']} of {w} date windows{short}{cells('cells_same_direction')}. "
        f"It is significant in {counts['windows_significant']} of {w} date windows{cells('cells_significant')}. "
        "Nearby cells and overlapping windows are not independent checks."
    )
    return counts


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
