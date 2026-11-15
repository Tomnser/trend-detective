# Trend Detective: climate finding checker

A Streamlit app that shows how an environmental variable has changed at a place, how strong the evidence is, and whether the finding survives reasonable changes of date window, neighbouring grid cell, method and coverage rule. NASA Space Apps 2026.

The app only ever shows real NASA data. If data cannot be loaded, it shows an error and suggests a preset. It never falls back to synthetic values (the synthetic generator `tests/demo_data.py` exists for tests only).

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

No token is needed for the 7 preset places × 3 variables: every series the app uses, including the neighbour cells, is in `cache/`. To fetch new places or periods, put an Earthdata Login token in `.env` (never committed):

```
EDL_TOKEN=<your Earthdata Login bearer token>
```

Tests (offline, cache only):

```bash
pytest -s tests/
```

## Where the data come from

All series come from the NASA GES DISC **Giovanni time-series API** (`https://api.giovanni.earthdata.nasa.gov/timeseries`). Each response is one grid cell's monthly series as CSV with a metadata header. The cache keeps the raw CSV, so the provenance travels with the data.

| Key | Giovanni ID | Product · DOI | Source unit → shown as | Period | Grid |
|---|---|---|---|---|---|
| `MERRA2_T2M` | `M2IMNXASM_5_12_4_T2M` (version 5.12.4) | MERRA-2 M2IMNXASM · 10.5067/5ESKGQTZG7FO | K → °C (−273.15) | 1981-01 – 2025-12 | 0.5° × 0.625° |
| `GPM_PRECIP` | `GPM_3IMERGM_07_precipitation` | GPM IMERG Final monthly V07 · 10.5067/GPM/IMERG/3B-MONTH/07 | mm/hr → mm/month (× 24 × days in month) | 2001-01 – 2025-09 | 0.1° × 0.1° |
| `GLDAS_SSM` | `GLDAS_NOAH025_M_2_1_SoilMoi0_10cm_inst` | GLDAS Noah 2.1 monthly · 10.5067/SXAVCZFAQLNO | kg m⁻² = mm water in the top 10 cm (no change) | 2001-01 – 2025-12 | 0.25° × 0.25° |

- The `unit` line of every CSV is checked against the catalogue before converting. A mismatch is an error.
- Missing values (the file's `undef` code) become NaN. Missing months stay explicit and are never filled.
- Trailing months that are not yet processed (GPM after 2025-09) are trimmed.
- Results describe **one grid cell**, not a city. The app shows the requested point next to the returned cell centre. When two places fall in the same grid cell, the app says so. No two presets share a cell.

## Method (short)

- **Anomalies:** each month minus that calendar month's mean over the full record (a fixed climatology).
- **Trend and verdict:** OLS slope of the monthly anomalies. The **verdict uses the adjusted-OLS p-value**: the OLS standard error inflated by an AR(1) effective sample size. It gave 4% to 8% false positives in our simulations of 10 to 45 years (`scripts/calibration_grid.txt`); real series can be more complex.
- **Cross-checks:** the Newey–West HAC p-value and 95% interval (fixed 12-month Bartlett lag) is a cross-check only. The seasonal Sen slope is shown as descriptive only; seasonal Mann–Kendall gave 22% false positives in the same simulation and is not used.
- **Warnings** appear when Sen's sign disagrees with OLS, or when the HAC and adjusted-OLS p-values fall on opposite sides of 0.05.
- **Years needed:** Weatherhead et al. (1998), using the residual SD, the lag-1 autocorrelation clipped to [0, 0.95], and the slope per year.
- **Coverage rule:** at least 10 complete years (all 12 months), at least 80% of months overall, and at least 70% for every calendar month.
- **Challenges:**
  - start years first_year, 1991, 2001, 2011 and 2016 (only windows with at least 10 complete years)
  - 4 neighbouring cells about 0.5° away, snapped to the dataset grid around the returned cell, each with its own climatology
  - the OLS, HAC and Sen method rows
  - two coverage thresholds
  - a summary line, "k of N cells significant": cells are spatially correlated, so these are not independent confirmations

## Files

| File | Role | Owner |
|---|---|---|
| `data_access.py` | Giovanni API client, raw-CSV cache, app-facing loaders, shared-cell lookup | Person 1 (data + stats) |
| `processing.py` | CSV parser, unit converters, coverage rule, climatology/anomalies, Sen slope | Person 1 |
| `catalogue.py` | variables (IDs, units, periods), preset places | Person 1 |
| `analysis.py` | trend engine: OLS + AR(1) adjustment, HAC, Weatherhead years-needed, warnings | Person 1 |
| `challenge.py` | date / neighbour / method / coverage challenges, regional summary | Person 1 |
| `tests/` | pytest suite (HAC vs statsmodels, null simulation, Milan table, challenge rows, notes) | Person 1 |
| `cache/` | committed Giovanni CSVs (offline demo) | Person 1 |
| `app.py` | Streamlit interface | Person 2 (interface) |
| `explanations.py` | plain-language result summary | Person 2 |
| `contracts.py` | shared dataclasses (`Plan`, `TrendResult`, `ChallengeRow`) | shared |
| `scripts/` | smoke test, data checks, challenge check, robustness report (`robustness_report.txt`) | Person 1 |

**The app is `app.py`.** An earlier standalone prototype with an AI "evidence advisor" (`adapp.py`, Person 2) is kept on branch `p2-advisor`. It has its own statistics, is not tested and is not part of the app.

## Preset places

Milan and the Po Valley (northern Italy), Seville (Mediterranean), Niamey (Sahel), Fairbanks (subarctic), the Sierra Nevada of California (mountain snow) and the Murray–Darling Basin (semi-arid, Southern Hemisphere). The five places outside Italy were chosen for their climate and for complete data coverage, before looking at any trend result. Each is cached with its 4 neighbour cells.

## Use of AI

- The app has **no AI feature**. Every number on screen is computed by the code in this repository from NASA data.
- Anthropic's Claude (Claude Code) was used as a coding assistant for the data layer, the trend engine, the tests and this README. The team chose the methods, approved each statistical decision and checked the results against the reference numbers in `ROADMAP.md`.
- An earlier prototype, `adapp.py`, calls an OpenAI model for an "evidence advisor". It is kept on branch `p2-advisor` and is not part of the app.
- No AI-generated images, audio or video are used. No NASA branding was altered.

## References

**Data** (NASA GES DISC, through the Giovanni time-series API, https://api.giovanni.earthdata.nasa.gov/timeseries)

- Global Modeling and Assimilation Office (GMAO). MERRA-2 instM_2d_asm_Nx: 2d, Monthly mean, Single-Level, Assimilation, Single-Level Diagnostics V5.12.4 (M2IMNXASM). doi:10.5067/5ESKGQTZG7FO
- Huffman, G. J., et al. GPM IMERG Final Precipitation L3 1 month 0.1 degree x 0.1 degree V07 (GPM_3IMERGM). doi:10.5067/GPM/IMERG/3B-MONTH/07
- Beaudoing, H., and M. Rodell. GLDAS Noah Land Surface Model L4 monthly 0.25 x 0.25 degree V2.1 (GLDAS_NOAH025_M). doi:10.5067/SXAVCZFAQLNO

The retrieval date of every series is in its cached CSV (`Request_time`) and is shown in the app.

**Methods**

- Weatherhead, E. C., et al. (1998). Factors affecting the detection of trends: Statistical considerations and applications to environmental data. *Journal of Geophysical Research*, 103(D14), 17149–17161. doi:10.1029/98JD00995
- Newey, W. K., and K. D. West (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703–708. doi:10.2307/1913610
- Benjamini, Y., and Y. Hochberg (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society B*, 57(1), 289–300. doi:10.1111/j.2517-6161.1995.tb02031.x
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the American Statistical Association*, 63(324), 1379–1389. doi:10.1080/01621459.1968.10480934
- Hirsch, R. M., J. R. Slack and R. A. Smith (1982). Techniques of trend analysis for monthly water quality data. *Water Resources Research*, 18(1), 107–121. doi:10.1029/WR018i001p00107

**Software**

Python 3.11, Streamlit 1.67.0, pandas, NumPy, SciPy, statsmodels, Plotly, requests, python-dotenv, pytest. Versions are in `requirements.txt`.
