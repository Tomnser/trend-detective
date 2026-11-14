"""Fetch monthly point time series from the Giovanni API, with an on-disk cache."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from processing import parse_giovanni_csv

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
API_URL = "https://api.giovanni.earthdata.nasa.gov/timeseries"

load_dotenv(ROOT / ".env")


def _month(ts: str) -> pd.Timestamp:
    return pd.Timestamp(ts).to_period("M").to_timestamp()  # first of month


def cache_path(var_id: str, lat: float, lon: float, start: str, end: str) -> Path:
    s, e = _month(start).strftime("%Y-%m"), _month(end).strftime("%Y-%m")
    return CACHE_DIR / f"{var_id}_{lat:.2f}_{lon:.2f}_{s}_{e}.csv"


def _version_of(var_id: str) -> str:
    # M2IMNXASM_5_12_4_T2M -> 5.12.4
    return ".".join(var_id.split("_")[1:4])


def fetch_csv(var_id: str, lat: float, lon: float, start: str, end: str,
              retries: int = 3, timeout: int = 120) -> str:
    token = os.environ.get("EDL_TOKEN")
    if not token:
        raise RuntimeError("EDL_TOKEN not set (add it to .env)")
    t0 = _month(start)
    t1 = _month(end) + pd.offsets.MonthEnd(0)
    params = {
        "data": var_id,
        "location": f"[{lat:.2f},{lon:.2f}]",
        "time": f"{t0:%Y-%m-%d}T00:00:00/{t1:%Y-%m-%d}T23:59:59",
        "version": _version_of(var_id),
    }
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


def get_monthly(var_id: str, lat: float, lon: float, start: str, end: str) -> pd.Series:
    """Monthly series (freq MS, NaN for missing months), cached as the raw CSV."""
    lat, lon = round(lat, 2), round(lon, 2)
    path = cache_path(var_id, lat, lon, start, end)
    if path.exists():
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
    s.attrs = {
        "var_id": var_id,
        "name": meta.get("param_name", var_id),
        "units": meta.get("unit"),
        "dataset": f"MERRA-2 {var_id.split('_')[0]}",
        "version": _version_of(var_id),
        "cell_lat": float(meta["lat"]) if "lat" in meta else None,
        "cell_lon": float(meta["lon"]) if "lon" in meta else None,
        "query_lat": lat,
        "query_lon": lon,
        "retrieved": meta.get("Request_time", "")[:10] or None,
    }
    return s
