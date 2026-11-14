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
