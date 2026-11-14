"""Fetch monthly point time series from the Giovanni API, with an on-disk cache."""
from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from catalogue import LAST_YEAR, PLACES, get_variable_meta, meta_for_api_id
from contracts import Plan
from processing import CONVERTERS, parse_giovanni_csv

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
API_URL = "https://api.giovanni.earthdata.nasa.gov/timeseries"

load_dotenv(ROOT / ".env")


def _month(ts: str) -> pd.Timestamp:
    return pd.Timestamp(ts).to_period("M").to_timestamp()  # first of month


def cache_path(var_id: str, lat: float, lon: float, start: str, end: str) -> Path:
    s, e = _month(start).strftime("%Y-%m"), _month(end).strftime("%Y-%m")
    return CACHE_DIR / f"{var_id}_{lat:.2f}_{lon:.2f}_{s}_{e}.csv"


def _api_version(var_id: str) -> str | None:
    meta = meta_for_api_id(var_id)
    return meta["api_version"] if meta else None


def fetch_csv(var_id: str, lat: float, lon: float, start: str, end: str,
              retries: int = 3, timeout: int = 120) -> str:
    token = os.environ.get("EDL_TOKEN")
    if not token:
        raise RuntimeError(f"No cached data for {var_id} at {lat:.2f}, {lon:.2f}, "
                           "and EDL_TOKEN is not set, so it cannot be downloaded.")
    t0 = _month(start)
    t1 = _month(end) + pd.offsets.MonthEnd(0)
    params = {
        "data": var_id,
        "location": f"[{lat:.2f},{lon:.2f}]",
        "time": f"{t0:%Y-%m-%d}T00:00:00/{t1:%Y-%m-%d}T23:59:59",
    }
    version = _api_version(var_id)
    if version is not None:
        params["version"] = version
    headers = {"Authorization": f"Bearer {token}"}
    err = ""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(API_URL, params=params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.text
            err = f"HTTP {r.status_code}: {r.text[:500]}"
            if r.status_code < 500:
                break  # client error: retrying won't help
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Giovanni fetch failed for {var_id} @ {lat},{lon}: {err}")


def _float_or_none(meta: dict[str, str], key: str) -> float | None:
    return round(float(meta[key]), 4) if key in meta else None


def get_monthly(var_id: str, lat: float, lon: float, start: str, end: str) -> pd.Series:
    """Monthly series in source units (freq MS, NaN for missing months), cached as the raw CSV."""
    lat, lon = round(lat, 2), round(lon, 2)
    path = cache_path(var_id, lat, lon, start, end)
    from_cache = path.exists()
    if from_cache:
        text = path.read_text()
    else:
        text = fetch_csv(var_id, lat, lon, start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text)
        tmp.replace(path)

    meta, raw = parse_giovanni_csv(text)
    if not (raw.index == raw.index.to_period("M").to_timestamp()).all():
        raise ValueError("timestamps are not first-of-month 00:00")
    full = pd.date_range(_month(start), _month(end), freq="MS")
    s = raw.reindex(full).astype(float)
    s.index.name = "time"
    s.name = var_id
    prod = meta.get("prod_name", var_id)
    s.attrs = {
        "var_id": var_id,
        "name": meta.get("param_name", var_id),
        "units": meta.get("unit"),
        "dataset": prod,
        "version": _api_version(var_id) or (prod.split(".", 1)[1] if "." in prod else None),
        "doi": meta.get("doi"),
        "cell_lat": _float_or_none(meta, "lat"),
        "cell_lon": _float_or_none(meta, "lon"),
        "lat_res": _float_or_none(meta, "lat_resolution"),
        "lon_res": _float_or_none(meta, "lon_resolution"),
        "query_lat": lat,
        "query_lon": lon,
        "retrieved": meta.get("Request_time", "")[:10] or None,
        "from_cache": from_cache,
    }
    return s


# ---------------------------------------------------------------------------
# App-facing loaders (same signatures as tests/demo_data.py)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=128)
def _full_series_cached(variable_name: str, lat: float, lon: float) -> pd.Series:
    meta = get_variable_meta(variable_name)
    if meta is None:
        raise ValueError(f"Unsupported variable: {variable_name}")
    raw = get_monthly(meta["api_id"], lat, lon, f"{meta['first_year']}-01", f"{LAST_YEAR}-12")
    if raw.attrs["units"] != meta["source_unit"]:
        raise ValueError(f"{variable_name}: Giovanni returned units {raw.attrs['units']!r}, "
                         f"expected {meta['source_unit']!r}; refusing to convert.")
    s = CONVERTERS[meta["converter"]](raw)
    if s.attrs["units"] != meta["display_unit"]:
        s.attrs["units"] = meta["display_unit"]
    s.attrs["source_units"] = meta["source_unit"]
    last = s.last_valid_index()
    if last is None:
        raise ValueError(f"{variable_name} at {lat:.2f}, {lon:.2f}: the source returned no valid months.")
    attrs = s.attrs
    s = s.loc[:last]  # trim trailing all-NaN months (e.g. not yet processed)
    s.attrs = attrs
    s.name = variable_name
    return s


def _copy(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.attrs = dict(s.attrs)
    return out


def load_full_series(variable_name: str, place: str = "Milan", lat: float = 45.46, lon: float = 9.19) -> pd.Series:
    """Full record (first_year-01 .. last valid month) in display units. `place` is unused."""
    return _copy(_full_series_cached(variable_name, round(lat, 2), round(lon, 2)))


def load_series_for_plan(plan: Plan, variable_name: str | None = None, *, full_record: bool = False) -> pd.Series:
    variable = variable_name or (plan.variables[0] if plan.variables else "MERRA2_T2M")
    full = load_full_series(variable, plan.place, plan.lat, plan.lon)
    if full_record:
        return full
    start = pd.Timestamp(plan.start).to_period("M").to_timestamp()
    end = pd.Timestamp(plan.end).to_period("M").to_timestamp()
    # Reindex so absent months stay explicitly missing.
    window = full.reindex(pd.date_range(start, end, freq="MS")).rename(variable)
    window.index.name = full.index.name
    window.attrs = dict(full.attrs)
    return window


def load_plan_metadata(plan: Plan) -> dict:
    variable = plan.variables[0] if plan.variables else "MERRA2_T2M"
    a = load_full_series(variable, plan.place, plan.lat, plan.lon).attrs
    return {
        "dataset": a.get("dataset"),
        "version": a.get("version"),
        "doi": a.get("doi"),
        "place": plan.place,
        "requested_coordinates": {"lat": a.get("query_lat"), "lon": a.get("query_lon")},
        "resolved_cell_coordinates": {"lat": a.get("cell_lat"), "lon": a.get("cell_lon")},
        "grid_resolution": {"lat": a.get("lat_res"), "lon": a.get("lon_res")},
        "retrieval_time": a.get("retrieved"),
        "units": a.get("units"),
        "from_cache": a.get("from_cache"),
    }


def places_sharing_cell(variable_name: str, place: str) -> list[str]:
    """Other preset places whose point falls in the same grid cell as `place` for this variable."""
    def cell(name: str) -> tuple[float, float]:
        lat, lon = PLACES[name]
        a = load_full_series(variable_name, name, lat, lon).attrs
        return (a["cell_lat"], a["cell_lon"])

    mine = cell(place)
    shared = []
    for other in PLACES:
        if other == place:
            continue
        try:
            if cell(other) == mine:
                shared.append(other)
        except (RuntimeError, ValueError, OSError):
            continue  # cannot load the other place: no claim either way
    return shared
