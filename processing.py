"""Parsing and basic processing of Giovanni time-series CSVs."""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

HEADER = "Timestamp (UTC),Data"
KELVIN_OFFSET = 273.15


def split_giovanni_csv(text: str) -> tuple[dict[str, str], str]:
    """Split a Giovanni CSV into (metadata dict, data block incl. header line).

    Format seen from the API: `key,value` lines, a blank line, then
    `Timestamp (UTC),Data` followed by `YYYY-MM-DD HH:MM,value` rows.
    """
    lines = text.splitlines()
    try:
        h = next(i for i, ln in enumerate(lines) if ln.strip() == HEADER)
    except StopIteration:
        raise ValueError(f"header {HEADER!r} not found; first lines: {lines[:20]}")
    meta: dict[str, str] = {}
    for ln in lines[:h]:
        if "," in ln:
            k, v = ln.split(",", 1)
            meta[k.strip()] = v.strip()
    return meta, "\n".join(lines[h:])


def parse_giovanni_csv(text: str) -> tuple[dict[str, str], pd.Series]:
    """Return (metadata, raw Series indexed by timestamp). Fill values -> NaN."""
    meta, block = split_giovanni_csv(text)
    df = pd.read_csv(io.StringIO(block))
    idx = pd.to_datetime(df["Timestamp (UTC)"], format="%Y-%m-%d %H:%M")
    s = pd.Series(pd.to_numeric(df["Data"], errors="coerce").to_numpy(float), index=idx)
    undef = float(meta.get("undef", "nan"))
    if np.isfinite(undef):
        s[np.isclose(s, undef, rtol=1e-6)] = np.nan
    if s.index.has_duplicates:
        raise ValueError(f"duplicate timestamps: {s.index[s.index.duplicated()].tolist()}")
    return meta, s.sort_index()


def to_celsius(s: pd.Series) -> pd.Series:
    """Kelvin -> °C. Refuses to convert a series not labelled K."""
    units = s.attrs.get("units")
    if units not in (None, "K"):
        raise ValueError(f"expected units K, got {units!r}")
    out = s - KELVIN_OFFSET
    out.attrs = {**s.attrs, "units": "°C"}
    return out


def coverage(s: pd.Series) -> dict[str, float]:
    """Data completeness of a monthly series.

    - frac_present: fraction of months that are not NaN
    - full_years: number of calendar years with all 12 months present
    - min_month_frac: over the 12 calendar months, the minimum fraction of
      years in which that month is present
    """
    present = s.notna()
    years = s.index.year
    per_year = present.groupby(years).sum()
    per_month = present.groupby(s.index.month).sum() / years.nunique()
    per_month = per_month.reindex(range(1, 13), fill_value=0.0)
    return {
        "frac_present": float(present.mean()),
        "full_years": int((per_year == 12).sum()),
        "min_month_frac": float(per_month.min()),
    }


# ---------------------------------------------------------------------------
# Analysis helpers (from Person 2, appended unchanged)
# ---------------------------------------------------------------------------

def climatology_for(series: pd.Series) -> pd.Series:
    clean = series.dropna().sort_index()
    if clean.empty:
        return pd.Series(dtype=float)
    return clean.groupby(clean.index.month).mean().sort_index()


def anomaly_series(series: pd.Series, climatology: pd.Series | None = None) -> pd.Series:
    ordered = series.sort_index().astype(float)
    if climatology is None:
        climatology = climatology_for(ordered)
    if ordered.empty or climatology.empty:
        return pd.Series(index=ordered.index, dtype=float, name=series.name)
    month_means = ordered.index.month.map(climatology)
    return pd.Series(ordered.to_numpy() - np.asarray(month_means, dtype=float), index=ordered.index, name=series.name)


def monthly_coverage(series: pd.Series) -> dict:
    if series.empty:
        return {"months_present": 0.0, "full_years": 0, "months_per_year": {}}
    start = series.index.min().to_period("M").to_timestamp()
    end = series.index.max().to_period("M").to_timestamp()
    expected = pd.date_range(start, end, freq="MS")
    present = series.reindex(expected).notna()
    total_years = end.year - start.year + 1
    by_year = {}
    for year in range(start.year, end.year + 1):
        year_index = expected[expected.year == year]
        by_year[str(year)] = int(series.reindex(year_index).notna().sum())
    return {
        "months_present": float(present.sum() / len(expected)) if len(expected) else 0.0,
        "full_years": total_years,
        "months_per_year": by_year,
    }


def series_coverage_ok(series: pd.Series, *, threshold: float = 0.80, month_threshold: float = 0.70, minimum_years: int = 10) -> tuple[bool, dict]:
    cov = monthly_coverage(series)
    if series.empty:
        return False, cov
    start = series.index.min().to_period("M").to_timestamp()
    end = series.index.max().to_period("M").to_timestamp()
    expected = pd.date_range(start, end, freq="MS")
    month_fractions = {}
    for month in range(1, 13):
        expected_months = expected[expected.month == month]
        present = series.reindex(expected_months).notna().sum()
        month_fractions[month] = float(present / len(expected_months)) if len(expected_months) else 0.0
    cov["calendar_month_coverage"] = month_fractions
    ok = (
        cov["full_years"] >= minimum_years
        and cov["months_present"] >= threshold
        and all(value >= month_threshold for value in month_fractions.values())
    )
    return ok, cov


def seasonal_sen_slope(series: pd.Series) -> float:
    """Median within-calendar-month pairwise slope, expressed per decade."""
    clean = series.dropna().sort_index()
    slopes = []
    for month in range(1, 13):
        subset = clean[clean.index.month == month]
        years = subset.index.year.to_numpy(dtype=float)
        values = subset.to_numpy(dtype=float)
        for i in range(len(values) - 1):
            for j in range(i + 1, len(values)):
                if years[j] != years[i]:
                    slopes.append((values[j] - values[i]) / (years[j] - years[i]))
    return float(np.median(slopes) * 10.0) if slopes else 0.0
