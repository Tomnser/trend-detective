You are working on **Trend Detective**, a Streamlit app for the NASA Space Apps Challenge 2026, challenge "Be an Earth System Trend Detective". Two people build it. The local demo is Sunday 15 November at 13:30. The final submission closes Sunday at 23:59.

## What the app is

A user picks a place and a variable. The app shows the NASA time series, the trend, how sure we are, and whether the finding survives other reasonable choices. The audience is high-school and college students. The guiding sentence is: "We don't tell you what's true. We show you how to check."

## Read first

1. `ROADMAP.md` — the task list. It is the only source of what to build and in which order.
2. `README.md` — data sources, method, file roles.
3. `contracts.py`, `analysis.py`, `challenge.py`, `processing.py`, `data_access.py`, `catalogue.py`, `app.py`, `explanations.py`.
4. `tests/` — run `pytest -s tests/` once before you change anything. All tests must pass.

## Which tasks are yours

The roadmap has blocks A to F. Tasks carry tags: `[E]` engine and data, `[U]` interface. I tell you which tag or which task ids this session owns. Take the first unchecked task among them unless I name another. Do not take a task that belongs to the other person.

## How we work (every turn)

1. **One roadmap task per turn.**
2. **Plan before code,** in four short parts: what changes and why; files and interfaces affected; decisions that need my approval; how you will verify.
3. **Wait for "go"** when the task is tagged `[A]`, or when it touches any of these: `contracts.py`, the verdict rule, a statistical method, a unit conversion, the coverage rule, the cache format, a new dependency, or product scope. For other tasks, state the plan and continue.
4. **Implement, then verify.** Run `pytest -s tests/`, including the app smoke test (`tests/test_app_smoke.py`, built in task A3). For interface work, start the app and describe what you saw.
5. **Report and stop.** What changed; test results; assumptions you could not verify; any deviation from the agreed method; the next recommended task. Do not start the next task.
6. **Tick the box** in `ROADMAP.md` in the same commit.

## Do not overshoot

- **Build the smallest thing that passes the task's check.** The roadmap text is the full specification. Add nothing it does not name: no extra options, settings, charts, abstractions or "while I'm here" fixes.
- **Time box: 45 minutes per task.** If your plan needs more, or more than 3 files, or more than about 150 new lines, stop before coding and propose a smaller version.
- **If a task runs over its box,** stop, commit nothing broken, and give me three options: finish (with a time estimate), ship a reduced version, or drop it.
- **Respect the cut line.** Do not start a task listed as upside in the "Cut line" section until I say the protected set is done. Never build anything in the roadmap's "Cut" list.
- **No rewrites.** Extend the existing functions. If you believe a rewrite is needed, say why and wait.
- **Live NASA calls are scarce.** State how many API calls a task needs. Ask before making more than 10 in one task. Never loop over places or variables without a stated count.
- **After Sunday 09:30,** bug fixes only, until I lift the freeze.
- **Ideas go in the report, not in the code.** If you see something worth doing, write one line under "Not done, for later".

## Hard rules

- Never change a statistical method, a data contract or the product scope silently. Ask first.
- The verdict comes from the adjusted-OLS p-value (OLS on monthly anomalies, AR(1) effective sample size). HAC and Sen are cross-checks. Do not change this.
- Anomalies use the fixed full-record calendar-month climatology. Missing months stay NaN. Never fill or interpolate.
- The app shows real NASA data only. Synthetic data is for tests.
- Every result describes one grid cell. Keep the cell centre, dataset, DOI and retrieval date visible.
- **New variables (task D4):** read the exact `unit` line from one real response before you write a converter. Show me the unit, the proposed conversion and the display unit, and wait for "go". A unit mismatch is an error, never a guess.
- **New places (tasks D2, D3):** I approve the preset list before any fetch. Choose places for scientific reasons, never because their results look significant. for a point over water or outside coverage, show a clear message. Never move the point silently.
- New numbers for the interface go into `TrendResult.settings`. Do not add fields to the dataclasses without approval.
- Do not edit `adapp.py` or the branch `p2-advisor`. Task A6 (moving the file to that branch) runs only after I confirm that my teammate agreed.
- The Earthdata token is in `.env` as `EDL_TOKEN`. Never print it, log it or commit it. Tasks tagged `[T]` need it; commit the new files in `cache/` after a fetch.
- Do not write a number into interface copy unless the engine computed it in this session or it is in the "Reference numbers" table of `ROADMAP.md`.

## Git

- `git pull --rebase` before each task. My teammate pushes to the same branch.
- One commit per task. Message format: `C2: window explorer with cached grid`.
- Push only when the tests pass and the app starts.
- If a pull brings a conflict in a file you did not plan to edit, stop and tell me.

## File ownership

- Engine and data (`analysis.py`, `challenge.py`, `processing.py`, `catalogue.py`, `data_access.py`, `tests/`, `cache/`, `scripts/`): Tommaso.
- Interface (`app.py`, `explanations.py`, `panels/`): new panels go in `panels/<name>.py`, one panel per file, each with a single `render(bundle)` function. `app.py` only wires panels together.
- `contracts.py`: change only after I confirm that both of us agreed.

## Streamlit rules

- Stay on Streamlit. No other framework, no custom JavaScript components, no separate back end.
- Cache with `st.cache_data`: series, window grids, challenge rows. Cache keys include place, variable and dates.
- Put interactive controls inside `st.fragment`. The window slider must respond without a full rerun.
- Precompute, then look up. The window grid is computed once per place and variable; the slider only selects a row.
- Keep the applied result in `st.session_state` when an input changes.
- Charts: Plotly. One palette for direction (up, down, unclear). Lines break at gaps.

## Interface copy rules

- First screen of a result: no p-value, no "HAC", no "effective n". Those live in an expander named "For the statistically curious".
- Every number has a unit. Slopes are "per decade", with the total change over the window where useful.
- Say "likely", never "proven". Say "this grid cell", never "this city".
- Significant is not the same as true. Not significant is not the same as no change. Window counts are a sensitivity analysis, never a proof.
- Short sentences. English. No exclamation marks.

## Definition of done

- The roadmap's check for the task holds, with the reference numbers where the roadmap gives them.
- `pytest -s tests/` passes, including the app smoke test.
- The app starts and the three example buttons still work.
- The change is committed and pushed, and the box is ticked.

## Start now

Read the files listed above. Run the tests. Then tell me:

1. the test result;
2. anything in the repository that contradicts `ROADMAP.md`;
3. which tasks you understood are mine (ask if I did not say);
4. the plan for the first unchecked one.

Then wait for my "go".
