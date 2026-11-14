"""Step 3 sanity checks for MERRA-2 T2M at Milan."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from data_access import cache_path, get_monthly  # noqa: E402
from processing import coverage, to_celsius  # noqa: E402

VAR, LAT, LON, START, END = "M2IMNXASM_5_12_4_T2M", 45.46, 9.19, "1981-01", "2025-12"


def main() -> None:
    cached = cache_path(VAR, LAT, LON, START, END).exists()
    s_k = get_monthly(VAR, LAT, LON, START, END)
    print(f"cache {'HIT' if cached else 'MISS (fetched)'}: {cache_path(VAR, LAT, LON, START, END).relative_to(ROOT)}")
    print("attrs:", s_k.attrs)
    print(f"index: {s_k.index[0]:%Y-%m} .. {s_k.index[-1]:%Y-%m}, freq={s_k.index.freqstr}, dtype={s_k.dtype}")
    print(f"rows: {len(s_k)} (expected 540)")
    missing = s_k.index[s_k.isna()]
    print(f"missing months: {len(missing)}", [f"{t:%Y-%m}" for t in missing][:24])
    print("coverage:", coverage(s_k))
    print(f"raw range: {s_k.min():.2f} .. {s_k.max():.2f} {s_k.attrs['units']}")

    s = to_celsius(s_k)
    clim = s.groupby(s.index.month).agg(["mean", "min", "max"]).round(2)
    clim.index.name = "month"
    print("\nmonthly climatology 1981-2025 (°C):")
    print(clim.to_string())
    jan, jul = clim.loc[1, "mean"], clim.loc[7, "mean"]
    print(f"\nJan mean {jan:.2f} °C (expect ~0-5): {'OK' if -1 <= jan <= 6 else 'CHECK'}")
    print(f"Jul mean {jul:.2f} °C (expect ~22-27): {'OK' if 21 <= jul <= 28 else 'CHECK'}")

    annual = s.groupby(s.index.year).mean()
    print("\nannual means (°C), first/last 5:")
    print(annual.head().round(2).to_string(), "\n...\n" + annual.tail().round(2).to_string())

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(s.index, s, lw=0.7, color="0.6", label="monthly")
    ax.plot(s.index, s.rolling(12, center=True, min_periods=12).mean(), lw=2,
            color="tab:red", label="12-month rolling mean (centred)")
    a = s.attrs
    ax.set_title(f"{a['dataset']} {a['name']} — cell centre {a['cell_lat']}N, {a['cell_lon']}E "
                 f"(query {LAT}, {LON})")
    ax.set_ylabel("°C")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = ROOT / "cache" / "check_t2m_milan.png"
    fig.savefig(out, dpi=120)
    print(f"\nplot saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
