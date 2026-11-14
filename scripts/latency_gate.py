"""Latency gate (task D1): time one live full-record Giovanni fetch per variable.

Point outside the cache: Seville (37.39, -5.99). Exactly 3 calls, one attempt each, no retry.
Responses are written to cache/ in the normal format, so the calls are not wasted.
Run: python scripts/latency_gate.py   (needs EDL_TOKEN in .env)
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalogue import LAST_YEAR, SUPPORTED_VARIABLES  # noqa: E402
from data_access import cache_path, fetch_csv, get_monthly  # noqa: E402

LAT, LON = 37.39, -5.99
LIMIT_S = 20.0
OUT = ROOT / "scripts" / "latency_gate.txt"


def main() -> None:
    lines = [f"Latency gate, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Point {LAT}, {LON} (Seville). "
             "One attempt per variable, no retry, timeout 120 s."]
    worst, failures = 0.0, 0
    for name, meta in SUPPORTED_VARIABLES.items():
        start, end = f"{meta['first_year']}-01", f"{LAST_YEAR}-12"
        path = cache_path(meta["api_id"], LAT, LON, start, end)
        if path.exists():
            sys.exit(f"{path.name} is already cached: this would not be a live fetch. Nothing was called for it.")
        t0 = time.perf_counter()
        try:
            text = fetch_csv(meta["api_id"], LAT, LON, start, end, retries=1)
        except RuntimeError as error:
            seconds = time.perf_counter() - t0
            failures += 1
            lines.append(f"{name:11s} FAILED after {seconds:6.1f} s (includes a 2 s back-off): {str(error)[:200]}")
            continue
        seconds = time.perf_counter() - t0
        worst = max(worst, seconds)
        path.write_text(text)
        s = get_monthly(meta["api_id"], LAT, LON, start, end)  # read back from the cache, checks the format
        a = s.attrs
        lines.append(f"{name:11s} {seconds:6.1f} s  {len(text) / 1024:6.1f} kB  {start}..{end}  "
                     f"unit {a['units']!r}  cell {a['cell_lat']}, {a['cell_lon']}  "
                     f"{int(s.notna().sum())} of {len(s)} months present")
    if failures:
        verdict = f"GATE NOT PASSED: {failures} of 3 fetches failed."
    elif worst < LIMIT_S:
        verdict = f"GATE PASSED: slowest fetch {worst:.1f} s, under {LIMIT_S:.0f} s. Live 'any place' is safe."
    else:
        verdict = (f"GATE NOT PASSED: slowest fetch {worst:.1f} s, over {LIMIT_S:.0f} s. "
                   "'Any place' ships with a wait message; the demo uses presets.")
    lines.append(verdict)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
