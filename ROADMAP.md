# Trend Detective — roadmap rev 6

Written Sat 14 Nov 2026, 19:30. Replaces rev 5. Merges the direction review with the external assessment.
Keep this file in the repository root. Tick a box when the task is merged, tested and deployed.

**Product in one line:** Same data. Different conclusions. Trend Detective shows when to trust a trend, and when not to.

**Rule for every feature:** it must help a user answer one of five questions.

1. What was measured, and where?
2. How much did it change?
3. How strong is the statistical evidence?
4. Does the conclusion survive other reasonable choices?
5. What can we not conclude from the data?

## How to read a task

- `[E]` engine and data files: `analysis.py`, `challenge.py`, `processing.py`, `catalogue.py`, `data_access.py`, `tests/`, `cache/`, `scripts/`
- `[U]` interface files: `app.py`, `explanations.py`, `panels/`
- `[OPS]` deployment, repository, documents
- `[T]` needs the Earthdata token and network
- `[A]` needs explicit approval before code (statistical method, data contract, unit conversion, scope, team matter)

## Decisions

| # | Decision |
|---|---|
| D1 | Keep Streamlit. No framework change. |
| D2 | The differentiator is the window explorer. It gets the most effort. |
| D3 | Geographic diversity before variable count. 4 to 5 presets in different climates. At most 2 new variables, each tied to an investigation. |
| D4 | Presets are chosen on scientific grounds and coverage, before looking at results. Whatever the engine returns is shown. |
| D5 | The home screen starts from guided investigations. The free form stays, below them. |
| D6 | The farmer idea ships as one guided investigation (Po Valley growing season), not as a mode. |
| D7 | Window counts are presented as a sensitivity analysis, not as a proof. The Benjamini–Hochberg count is optional and labelled as approximate because the windows overlap. |
| D8 | New interface panels live in `panels/`, one file per panel. `app.py` only wires them. |

## Cut (not built for this hackathon)

Water-storage mode, GRACE, SWOT. AI advisor, correlations, CSV upload. A browser over hundreds of variables. Eight variables. Heat days. OMI NO₂, MODIS NDVI. Two-place comparison. Station validation. More statistical methods. Any rewrite.
`adapp.py` moves to branch `p2-advisor` after the team agrees.

## Schedule

| When | Block | Exit condition |
|---|---|---|
| Sat 19:30–20:15 | A. Secure | Public link opens in a private window. Smoke test exists. |
| Sat 20:15–22:00 | B. Understand | Plain result and predict → reveal work for the 3 examples. |
| Sat 20:15–00:30 | C. Differentiate | Window explorer and explainer work. |
| Sat 20:15–00:30 | D. Reach (parallel, engine side) | 4–5 presets cached. Any coordinates if the gate passes. |
| Sun 00:30–02:30 | E. Guide and polish | Investigation home screen, verdict card, theme. Redeploy. Tag `v-night`. |
| Sun 07:00–09:30 | F. Present | Slides and project page. **Freeze 09:30.** Tag `v-local-demo`. First submission save. |
| Sun 09:30–15:30 | Rehearse, table rounds, pitch | |
| Sun 16:00–22:00 | Leftover tasks from D and E only | Each one deployed and checked, or reverted. |
| Sun 22:30 | Final submission save | Banner seen. Deadline 23:59. |

## A. Secure (45 min)

- [x] **A1 `[OPS]` Commit `ROADMAP.md` and `CLAUDE.md`** in their own commit and push.
- [x] **A2 `[OPS]` Pin Streamlit** in `requirements.txt` to the local version (1.67.0).
- [x] **A3 `[E]` App smoke test,** `tests/test_app_smoke.py` with `streamlit.testing.v1.AppTest`: load the app, click each example, press "Check the finding", assert no exception.
- [x] **A4 `[OPS]` Deploy `main`** to Streamlit Community Cloud, Python 3.11, `EDL_TOKEN` as a secret. Open the link in a private window.
- [x] **A5 `[U]` `[A]` Fix example 3:** Po Valley rain, 2013-01 to 2022-12, label "Was the Po Valley drying? (the view from 2022)". `EXAMPLES` gains an end year. Check: -39.3 mm/month per decade, p = 0.024.
- [ ] **A6 `[OPS]` `[A]` Move `adapp.py`** to branch `p2-advisor`. Team agreement first.

## B. Understand (about 1.5 hours)

- [x] **B1 `[U]` Plain-language result.** Headline with unit and total change. Interval in words. A line "What we cannot conclude" (one grid cell, a linear model, no cause). Move p-value, effective n and HAC into an expander "For the statistically curious". Remove the three permanent method notes from the main view.
- [x] **B2 `[U]` Predict → reveal.** Before the result: Rising / Falling / No clear trend. After: "The data support your prediction", "The data point the other way", or "Not enough evidence either way". Add: "Not significant does not mean nothing is changing."
- [x] **B3 `[E]` + `[U]` `[A]` Evidence line for "not enough evidence".** The smallest trend this record can detect (Weatherhead inverted). Years needed only under 100 years, labelled "a rough, model-dependent estimate".

## C. Differentiate: the window explorer (about 3.5 hours, most effort)

- [x] **C1 `[E]` `[A]` Window grid.** `challenge.window_grid(plan, variable)`: one engine fit for every start and end year with at least 10 complete years. Same engine, same fixed climatology. Returns a DataFrame (start, end, slope, ci, p, verdict). Tests use the reference numbers below.
- [x] **C2 `[U]` Window explorer.** A two-handle year slider inside `st.fragment`. Chart, slope and verdict update at once from the cached grid. Beside it a heat map: start year × end year, colour = direction, strong colour = significant. The selected window is marked. The baseline result stays pinned above.
- [x] **C3 `[U]` `[A]` Sensitivity sentence.** From the grid: "Of 135 possible windows, 19 look significant: 8 say drier and 11 say wetter." Then: "These windows overlap, so they are not independent tests. The lesson is that the conclusion depends on the window." Optional second line with the Benjamini–Hochberg count, labelled approximate.
- [x] **C4 `[E]` + `[U]` "How we got this" explainer.** Four steps with the real numbers and a mini chart each: raw monthly data; remove the seasonal cycle (raw / deseasonalised toggle); fit the trend; judge the uncertainty. Numbers travel in `TrendResult.settings`.
- [x] **C5 `[E]` + `[U]` Robustness sentence above the challenge table,** real counts only, for date windows and nearby cells. Remove the two coverage rows. Collapse the table by default.
- [x] **C6 `[E]` `[A]` Honest statistics wording.** HAC warning: "HAC rejects too often on short records and on series with strong month-to-month memory; the verdict uses the adjusted test." Verdict rule: "4% to 8% false positives in our simulations of 10 to 45 years; real series can be more complex." Add `scripts/calibration_grid.py` with its output file.

## D. Reach: places first (parallel, about 3 hours)

- [x] **D1 `[E]` `[T]` Latency gate.** Time one live full-record fetch per variable for a point outside the cache (Seville, 37.39, -5.99). 3 calls, no retry. Under about 20 seconds: live "any place" is safe. Over: it ships with a wait message and the demo uses presets.
- [x] **D2 `[E]` `[T]` `[A]` Presets in different climates,** 4 to 5 beside the Po Valley and Milan. Propose a list with a one-line scientific reason and a coverage check for each (GLDAS is masked over water and ice; check GPM at high latitude). I approve the list before any fetch. Cache each with its 4 neighbours. Remove Bergamo (same MERRA-2 cell as Milan).
- [ ] **D3 `[E]` + `[U]` `[T]` Any coordinates.** Latitude/longitude input. Baseline cell first; neighbour cells only when the user opens that check. `[A]`: for a point over water or outside coverage, show a clear message and offer the nearest land cell; never move the point silently.
- [ ] **D4 `[E]` `[T]` `[A]` One or two purposeful variables.** Snow water equivalent (`GLDAS_NOAH025_M_2_1_SWE_inst`) for a mountain preset. Evapotranspiration (`..._Evap_tavg`) only if an investigation uses it. For each: the exact unit line from one real response, converter, definition, one test.
- [ ] **D5 `[U]` Variable help.** Each variable shows a two-line definition and "good for asking…" examples. The Theme selector goes away if it only repeats the Variable selector.

## E. Guide and polish (about 2 hours)

- [x] **E1 `[U]` Investigation home screen.** Cards: "How much has Milan warmed?", "Is the Po Valley getting drier?", "Was the 2022 drought a trend?", plus one per new preset. One click loads place, variable and window, then asks for the prediction. "Build your own" opens the form.
- [x] **E2 `[E]` + `[U]` `[A]` Growing-season investigation.** `analysis.season_trend(series, months, how)`: one value per year, April–September. OLS slope, t-test, interval, plus Sen's slope as a second check and a leave-one-year-out range. Bar chart with 2022 highlighted. Copy: "2022 was the 2nd driest growing season of 25. An extreme year is not a trend: the 25 seasons show none (p = 0.40)."
- [x] **E3 `[U]` Verdict card and theme.** Large plain sentence, direction icon, the five questions as the layout of the result page. `.streamlit/config.toml`. One palette for up / down / unclear. One name: "Trend Detective".
- [ ] **E4 `[U]` Speed and states.** `st.cache_data` on series and grids. No full-page spinner after first load. Friendly loading and error states. Check at phone width.
- [ ] **E5 `[U]` Glossary tooltips and a small grid-cell depiction** (optional).

## F. Present (fixed times, never moved)

- [ ] **F1** Slides 1–7 in English with real screenshots. Story: one question, two opposite answers from the same data, how the tool exposes it.
- [ ] **F2** Project page: summary, description, NASA Data, References, Use of SI. README: AI-use note and References.
- [ ] **F3** Public links tested in a private window. Wake the app before every judging slot (it sleeps after 12 hours without traffic).
- [ ] **F4** "Submit for Judging" clicked and the banner seen. First save Sunday morning, final save by 22:30.

## Cut line

- Protect: A, B, C1–C4, D1–D2, E1, E3, F.
- Upside: C5, C6, D3–D5, E2, E4, E5. C6 is wording only and takes 20 minutes; do it if any time remains.

## Reference numbers (committed cache, engine at `4eb8420`)

| Case | Result |
|---|---|
| Po Valley rain, 2013–2022 | -39.3 mm/month per decade, p = 0.024, significant decrease |
| Po Valley rain, 2001–2022 | 0.0, p = 0.998 |
| Po Valley rain, 2001–2025 | +4.4, p = 0.32 |
| Po Valley rain, all windows with ≥ 10 complete years | 135 windows; 19 significant (8 down, 11 up); 1 after Benjamini–Hochberg; slopes from -39.3 to +53.8 |
| Po Valley soil moisture, all windows | 136 windows; 17 significant (15 down, 2 up) |
| Milan temperature, all windows | 666 windows; 416 significant, all up, none down |
| Milan temperature, 1981–2025 | +0.489 °C per decade, about 2.2 °C in total |
| Po Valley rain, April–September total per year | 25 seasons 2001–2025; +22.4 mm per decade, p = 0.40; 2022 = 352 mm, 2nd lowest; mean 481 mm |
| False-positive rate, adjusted OLS | 4% to 8% over 10–45 years and lag-1 autocorrelation 0.2–0.8 (AR(1) simulations) |
| False-positive rate, HAC (12-month lag) | 13.7% to 22.6% at 10 years; 7.1% to 12.4% at 45 years |
