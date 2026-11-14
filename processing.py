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


def mm_per_hour_to_mm_per_month(s: pd.Series) -> pd.Series:
    """Monthly-mean rate (mm/hr) -> monthly total: × 24 h × days in that month."""
    units = s.attrs.get("units")
    if units not in (None, "mm/hr"):
        raise ValueError(f"expected units mm/hr, got {units!r}")
    out = s * 24.0 * s.index.days_in_month.to_numpy()
    out.attrs = {**s.attrs, "units": "mm/month"}
    return out


def identity(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.attrs = dict(s.attrs)
    return out


CONVERTERS = {
    "kelvin_to_celsius": to_celsius,
    "mm_per_hour_to_mm_per_month": mm_per_hour_to_mm_per_month,
    "identity": identity,
}


def coverage(s: pd.Series) -> dict[str, float]:
    """Data completeness of a monthly series (index = every month of the window).

    - frac_present: fraction of months that are not NaN
    - full_years: number of calendar years with all 12 months present
    - min_month_frac: over the 12 calendar months, the minimum fraction of that
      month's occurrences in the window that are present
    """
    present = s.notna()
    per_year = present.groupby(s.index.year).sum()
    per_month = present.groupby(s.index.month).mean()
    per_month = per_month.reindex(range(1, 13), fill_value=0.0)
    return {
        "frac_present": float(present.mean()) if len(s) else 0.0,
        "full_years": int((per_year == 12).sum()),
        "min_month_frac": float(per_month.min()),
    }


def coverage_ok(s: pd.Series, *, threshold: float = 0.80, month_threshold: float = 0.70,
                min_years: int = 10) -> tuple[bool, dict[str, float]]:
    """Coverage rule: >= min_years complete years, >= threshold of months overall,
    and >= month_threshold for every calendar month."""
    cov = coverage(s)
    ok = (cov["full_years"] >= min_years and cov["frac_present"] >= threshold
          and cov["min_month_frac"] >= month_threshold)
    return ok, cov


# ---------------------------------------------------------------------------
# Analysis helpers (from Person 2)
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
