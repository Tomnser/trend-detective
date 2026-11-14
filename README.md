# Climate finding checker

A small Streamlit prototype for exploring how a climate trend finding changes under reasonable analytical choices.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app starts without secrets or a live NASA request. **Current data are deterministic synthetic demo data, not NASA measurements.** The app labels this clearly; do not use demo outputs as evidence about the climate.

## Implemented

- Stable shared dataclasses in `contracts.py`
- Structured Streamlit question form with location, theme, variable and date range
- Monthly series with missing months retained as missing
- Fixed full-record calendar-month climatology for anomaly calculation and date challenges
- OLS monthly-anomaly trend, rough AR(1) effective-sample-size adjustment, HAC/Newey–West 12-month cross-check and seasonal Sen slope
- Coverage checks and fixed date, region, method and coverage challenge rows
- Synthetic provider fallback so the interface works offline

## Not yet implemented

NASA Giovanni retrieval, Earthdata Login token handling, NASA POWER fallback, real-data cache, land-cell snapping, Mann–Kendall cross-check, and deployment. No credentials should be committed. Connect a real data provider before presenting results as observational findings.

## Data layer

Real NASA data access lives in two files, separate from the demo provider in `demo_data.py`:

- `data_access.py`: `get_monthly(var_id, lat, lon, start, end)` calls the Giovanni time-series API (`https://api.giovanni.earthdata.nasa.gov/timeseries`). It authenticates with an Earthdata Login token read from `EDL_TOKEN` in `.env` (never committed). It returns a monthly `pd.Series` (freq `MS`, NaN for missing months), with provenance in `s.attrs`: dataset, version, units, the requested point, the returned grid-cell centre and the retrieval date.
- `processing.py`: the Giovanni CSV parser (fill value `undef` → NaN), `to_celsius` and `coverage`. The analysis helpers listed above are in the same file.
- `cache/`: raw Giovanni CSVs, committed so the demo works offline. Example: MERRA-2 `M2IMNXASM_5_12_4_T2M` for Milan (query 45.46, 9.19 → cell centre 45.5, 9.375), 1981-01 to 2025-12, 540 months, none missing.
- `scripts/smoke_test.py` (raw API call) and `scripts/check_t2m_milan.py` (sanity checks and plot).

The Giovanni layer is not yet wired into the app: `app.py`, `analysis.py` and `challenge.py` still load synthetic data from `demo_data.py`.
