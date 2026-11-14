"""Smoke test: fetch one MERRA-2 monthly T2M series from the Giovanni time-series API."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

URL = "https://api.giovanni.earthdata.nasa.gov/timeseries"
VAR_ID = "M2IMNXASM_5_12_4_T2M"
LAT, LON = 45.46, 9.19
TIME = "1981-01-01T00:00:00/2025-12-31T23:59:59"
OUT = ROOT / "cache" / "raw" / f"{VAR_ID}_{LAT:.2f}_{LON:.2f}.csv"


def fetch(with_version: bool = True, retries: int = 3) -> requests.Response:
    token = os.environ.get("EDL_TOKEN")
    if not token:
        sys.exit("EDL_TOKEN not set (put it in .env)")
    params = {"data": VAR_ID, "location": f"[{LAT},{LON}]", "time": TIME}
    if with_version:
        params["version"] = "5.12.4"
    headers = {"Authorization": f"Bearer {token}"}
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(URL, params=params, headers=headers, timeout=120)
            print(f"attempt {attempt}: HTTP {r.status_code} ({r.url.split('?')[0]})")
            if r.status_code < 500:
                return r
        except requests.RequestException as e:
            last = e
            print(f"attempt {attempt}: {type(e).__name__}: {e}")
        time.sleep(2 ** attempt)
    if last:
        raise last
    return r


def main() -> None:
    with_version = "--no-version" not in sys.argv
    r = fetch(with_version=with_version)
    print("status:", r.status_code, "| content-type:", r.headers.get("content-type"))
    text = r.text
    if r.status_code != 200:
        print("BODY:\n", text[:2000])
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    lines = text.splitlines()
    print(f"saved {OUT.relative_to(ROOT)} ({len(text)} bytes, {len(lines)} lines)")
    print("---- first 30 lines ----")
    for i, line in enumerate(lines[:30]):
        print(f"{i:>3}: {line}")
    print("---- last 3 lines ----")
    for line in lines[-3:]:
        print("     " + line)
    n_data = sum(1 for ln in lines if ln[:4].isdigit() and ln[4:5] == "-")
    print("data rows (lines starting with YYYY-):", n_data)


if __name__ == "__main__":
    main()
