"""Phase 1 checks: fetch GPM + GLDAS for the 3 preset places and print a report."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from catalogue import LAST_YEAR, get_variable_meta  # noqa: E402
from data_access import cache_path, load_full_series  # noqa: E402
from processing import coverage  # noqa: E402

PLACES = {"Milan": (45.46, 9.19), "Po Valley": (45.00, 10.00), "Bergamo": (45.70, 9.68)}
VARIABLES = ["GPM_PRECIP", "GLDAS_SSM"]


def unit_line(path: Path) -> str:
    return next((ln for ln in path.read_text().splitlines() if ln.startswith("unit,")), "unit line MISSING")


def main() -> None:
    flags: list[str] = []
    for var in VARIABLES:
        meta = get_variable_meta(var)
        for place, (lat, lon) in PLACES.items():
            path = cache_path(meta["api_id"], lat, lon, f"{meta['first_year']}-01", f"{LAST_YEAR}-12")
            t0 = time.perf_counter()
            s = load_full_series(var, place, lat, lon)
            dt = time.perf_counter() - t0
            a = s.attrs
            print(f"\n=== {var} · {place} (query {lat:.2f}, {lon:.2f})")
            print(f"fetch: {dt:.1f} s ({'cache hit' if a['from_cache'] else 'downloaded'}) -> {path.name}")
            print(f"{unit_line(path)}  ->  display units: {a['units']}")
            print(f"returned cell centre: {a['cell_lat']}, {a['cell_lon']}  (grid {a['lat_res']} x {a['lon_res']})")
            print(f"dataset {a['dataset']} · version {a['version']} · doi {a['doi']} · retrieved {a['retrieved']}")
            print(f"range: {s.index[0]:%Y-%m} .. {s.index[-1]:%Y-%m}  ({len(s)} months after trimming trailing NaN)")
            print("first 3:", ", ".join(f"{t:%Y-%m}={v:.2f}" for t, v in s.head(3).items()))
            print("last 3: ", ", ".join(f"{t:%Y-%m}={v:.2f}" for t, v in s.tail(3).items()))
            print("coverage:", {k: round(v, 3) for k, v in coverage(s).items()})
            missing = s.index[s.isna()]
            if len(missing):
                print("missing months:", [f"{t:%Y-%m}" for t in missing][:20])
            if var == "GPM_PRECIP":
                jja = s[s.index.month.isin([6, 7, 8])]
                clim = s.groupby(s.index.month).mean()
                print(f"summer (JJA) mean {jja.mean():.1f} mm/month · monthly clim: "
                      + " ".join(f"{m}:{v:.0f}" for m, v in clim.items()))
                out = s[(s < 0) | (s > 400)]
                if len(out):
                    flags.append(f"{var} {place}: {len(out)} months outside 0-400: "
                                 + ", ".join(f"{t:%Y-%m}={v:.0f}" for t, v in out.items()))
            else:
                print(f"min {s.min():.2f} · mean {s.mean():.2f} · max {s.max():.2f} {a['units']}")
    print("\nFLAGS:", flags or "none")


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    main()
