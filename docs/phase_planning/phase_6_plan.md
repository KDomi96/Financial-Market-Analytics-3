# Phase 6 plan: web application

Status: complete. The serving decisions were adopted with the plan, and all
ten steps have been carried out; the findings are in
[Phase 6 analysis](phase_6_analysis.md) and the commands in
[deployment](../deployment.md). The planned commands below were run as
written, except that the full-pipeline container ran the tests in the same
`docker run` after the pipeline. The design and its reasons are in
[methodology](../methodology.md#api-and-web-application).

Phase 6 builds a FastAPI service and a Streamlit interface. A user supplies
closing prices for two stocks, and the service tests the pair for
cointegration, builds the spread and Z-scores, and generates signals with the
Phase 4 rules. A second route serves the saved Phase 5 LSTMs. The service
writes no files, and no new data are acquired. Most of the work is input
validation and reuse of code that Phases 3-5 have already verified.

## Inputs

The service reads saved files and never refits anything from earlier phases:

| Input | Used for |
| --- | --- |
| `configs/pair_selection.json` | Engle-Granger, ADF, and Johansen settings and the 0.05 level |
| `configs/statistical_baseline.json` | Entry and exit thresholds |
| `data/processed/master_historical.csv`, `master_unseen.csv`, `master_manifest.json` | Sample prices for the 15 pairs and the session calendar for forecasts; 2,156 sessions from 2018-01-02 to 2026-07-31, checked against the manifest hashes |
| `outputs/metrics/pair_selection/pair_ranking.csv` | Phase 3 evidence labels for all 15 pairs (all exploratory) |
| `artifacts/lstm/phase5_v2/<PAIR_ID>/final_20180102_20251231/` | Weights, metadata with embedded preprocessing, and `known_inference.json` for AMZN_META and NVDA_AMZN |

The reproduction check also reads `artifacts/statistical/phase3_v1/`,
`artifacts/statistical/phase4_v1/`,
`data/processed/statistical_baseline/unseen_zscores.csv` (290 rows), and
`outputs/backtests/statistical_baseline/phase4_v1/unseen/signals.csv` (290
rows), plus `outputs/predictions/lstm/phase5_v2/`.

## Adopted decisions

| Decision | Adopted rule | Main consequence |
| --- | --- | --- |
| Price input | One CSV with `Date` and a closing-price column per ticker, or the project's prices; rejected rather than repaired | One analysis path for both sources; no live fetching |
| Test | Phase 3 settings; cointegrated when `min(1, 2 * smaller directional p) <= 0.05` and the Johansen trace rank is one at 95% | No correction across pairs; I(1) checks are warnings |
| Windows | Fit on sessions up to a chosen fit end (at least 504); normalization from the final year before it; at least 20 sessions after | A 2025-12-31 fit end reproduces Phase 4's 250-session window |
| Signals | Phase 4 rules after the fit end, starting flat | Dated signals and long/short counts; no P&L |
| Failing pair | Test results only, unless the exploratory view is requested | The spread is never shown unlabelled for a pair that fails |
| Forecasts | Saved `phase5_v2` bundles for two pairs, their own fit, at least 39 sessions | Shown apart from the user's fit |
| Forecast calendar | Origins on or before 2026-07-31, the last session in the masters | No calendar library; later target dates are returned without dates |
| Serving containers | API and app read the saved models, masters, and Phase 3 tables from read-only mounts | Served forecasts match the reported ones; the batch image still rebuilds from raw snapshots |
| Sentiment page | None until the sentiment study has results | Decided before implementation starts, since that study comes first |

Results quoted in project documents use a 2025-12-31 fit end. Other fit ends
are exploration by the user, not evaluation. Hosting remains open; the mounts
work locally and from the submission archive, and a hosted deployment would
need another way to supply the saved files.

## Design

### Package layout

Calculations accept explicit data and settings; only `main.py` reads files.
New code imports the frozen modules without editing them: Phase 4 hashes
`trading/`, and Phase 5 also hashes `features/`, `models/`, `data/master.py`,
and `uv.lock`.

| Module | Responsibility | Reuses |
| --- | --- | --- |
| `api/prices.py` | Parse and validate the CSV into a dated table with `<TICKER>_Close` columns | none |
| `api/analysis.py` | Fit split, I(1) warnings, both directional tests, Johansen, verdict, windowed normalization, Z-scores, signals | `integration_tests`, `directional_test`, `johansen_test`, `adjust_pair_pvalues`, `apply_normalization`, `decide_signal` |
| `api/forecast.py` | Bundle registry, startup check, forecast with the project calendar, origin Z, and the day-five direction | `forecast_from_prices`, `spread_from_prices`, `apply_normalization` |
| `api/schemas.py` | Pydantic response models | none |
| `api/main.py` | FastAPI app, startup, routes, error mapping | the three modules above |

`directional_test` and `integration_tests` read the tickers from
`cfg["stocks"]`, so the analysis passes a copy of the Phase 3 settings with
`stocks` set to the two supplied tickers.
`analyse()` in `selection.py` runs all 15 pairs and is not reused.

### Price file

The header is `Date,<TICKER_A>,<TICKER_B>`. Tickers have 1-10 characters from
A-Z, digits, `.`, and `-`, and must differ. Dates use `YYYY-MM-DD`. A UTF-8
byte-order mark is accepted, since spreadsheet exports often add one. The
file is limited to 1 MB and 10,000 rows. Any duplicate or decreasing date,
empty cell, non-numeric value, `nan` or `inf`, or price at or below zero
rejects the whole file with a message naming the first bad row. The interface
sends the uploaded bytes unchanged; it never parses them.

### Analysis order

1. Split at the fit end. Count the sessions on or before it (at least 504) and
   after it (at least 20).
2. On fitting log prices, run the I(1) diagnostics for each ticker and keep
   them as warnings.
3. Run `directional_test` in both directions, keep the smaller Engle-Granger
   p-value, and compute the direction-adjusted p-value.
4. Run `johansen_test`. The verdict requires both rules.
5. If the pair passes or the exploratory view was requested, build the spread
   from the kept regression for every session. Fit the mean and `ddof=1`
   standard deviation on sessions later than `fit_end - DateOffset(years=1)`
   and up to the fit end, then apply them to every session.
6. Walk `decide_signal` over the sessions after the fit end, starting flat,
   with the last fitting Z-score as the first comparison. The position follows
   each action, because in Phase 4 a signal at one close is filled before the
   next.
7. For any two of the six project tickers, attach the Phase 3 label and the
   note that a single-pair test overstates the evidence for a pair chosen from
   a ranking.

### Routes

| Route | Success | Errors |
| --- | --- | --- |
| `GET /health` | Status, bundle versions, and the startup check result for each bundle | none; reports `degraded` if a bundle failed |
| `GET /pairs` | Six tickers, 15 pairs with labels, and which pairs have a bundle | none |
| `GET /samples/{pair}` | CSV of the pair's closing prices, 2,156 rows, in the upload format | 404 for an unknown pair |
| `POST /analyze` | Multipart file plus `fit_end` and `exploratory` form fields | 422 with the validation message |
| `POST /forecast` | Multipart file plus `pair` | 422 for a pair without a bundle, too few sessions, a missing session, or a late origin; 503 if that bundle failed at startup |

The statistical routes stay available when a bundle fails its startup check.
Streamlit calls the API from its own server process, so the browser never
contacts the API and no CORS setup is needed. The API address comes from the
`API_URL` environment variable, defaulting to `http://localhost:8000`.

## Steps

**1. Decide the sentiment page.** Done: no sentiment page or
route, so no extra mount. The sentiment study stays a separate experiment; the
reason is in
[methodology](../methodology.md#sentiment-in-the-application).

**2. Add the libraries.** Run `uv add fastapi uvicorn python-multipart streamlit
httpx`. `httpx` is a runtime dependency: the interface uses it to call the
API, and FastAPI's test client needs it in the Docker image, which installs
without the dev group. A trial resolution on a copy of the existing lock
kept all 91 locked packages at their versions and added 21 (FastAPI 0.162.0,
Uvicorn 0.54.0, python-multipart 0.0.33, Streamlit 1.66.1, httpx 0.28.1,
Pydantic 2.14.2). The sentiment libraries will have changed the lock by the
time this step runs, so repeat the comparison against the lock as it stands
then, and stop if any existing version changes. Then run the full test suite.

Done with uv 0.13.1. The lock went from 117 to 134 packages,
with no existing version changed or removed. The 17 additions are fewer than
the trial's 21 because the sentiment libraries had already brought in some of
the shared dependencies. The comparison is in
`outputs/metrics/api/phase6_lock_comparison.json`.

Once `uv.lock` differs from the one recorded in the Phase 5 contract, whether
through the sentiment libraries or these, `scripts/run_pipeline.py` refuses
to rerun Phase 5 against the existing evaluated outputs. That refusal is
intended. Do not rerun Phases 1-5 locally; a fresh Docker build has no earlier
outputs and runs all five.

**3. Write `configs/api.json`.** Input paths, the bundle directories, the size
and session limits, the alpha level, and the startup tolerance.

**4. Price input.** Implement `prices.py` with its tests before any route.

**5. Analysis.** Implement `analysis.py` and test it on synthetic series. Then
run the reproduction check on the project's prices (see Checks). Fix any
mismatch in the new code; never in the frozen modules.

**6. Forecasts.** Implement the registry and startup check, and compare a
served forecast with a saved Phase 5 unseen forecast.

**7. Routes.** Add schemas, routes, and error mapping, with test-client tests
for every route and status code.

**8. Interface.** Build `app/streamlit_app.py` with input controls (upload or
sample, fit end, exploratory option); the verdict with both tests, warnings,
and the Phase 3 note; spread and Z-score charts with the ±2 and 0 lines and
signal markers; the signal table and counts; and a forecast panel for the two
pairs with bundles, noting that persistence beat both models. Every number
shown comes from an API response.

**9. Docker.** Add `compose.yaml` with `api` and `app` services from the
existing image, with the read-only mounts and ports 8000 and 8501. The
Dockerfile's default command stays the batch pipeline. Rerun both pipeline
modes and the tests in a fresh image, because the lock has changed, and then
start the two services.

**10. Evidence and documents.** Run `/analyze` for all 15 project pairs with a
2025-12-31 fit end and save the verdicts. Capture interface screenshots for
the report. Write `phase_6_analysis.md`, log the run, and update README,
`deployment.md`, the directory guide, `.env.example`, and the local checklist.

## Files

| File | Responsibility |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Five new runtime libraries; no version already in the lock changed |
| `configs/api.json` | Paths, limits, alpha, and startup tolerance |
| `src/market_analytics/api/{__init__,prices,analysis,forecast,schemas,main}.py` | The service, as above |
| `app/streamlit_app.py` | The interface; HTTP calls only |
| `compose.yaml` | API and app services with read-only mounts |
| `.env.example` | `API_URL` with a blank value |
| `tests/test_api_prices.py` | Validation cases |
| `tests/test_api_analysis.py` | Synthetic verdicts, windows, signals, exploratory view, fit-window isolation |
| `tests/test_api_routes.py` | Every route and status code through the test client |
| `tests/test_api_reproduction.py` | Phase 3/4/5 agreement on project data; skips with a message when those outputs are absent |
| `outputs/metrics/api/project_pair_verdicts.csv` | Single-pair verdicts for the 15 project pairs at a 2025-12-31 fit end |
| `outputs/figures/app/` | Interface screenshots for the report |
| `outputs/metrics/phase6_review_validation.json`, `phase6_docker_validation.json` | Test results, reproduction results, lock comparison, frozen-code hashes, Docker runs |
| `docs/phase_planning/phase_6_analysis.md` | Findings from the verdict table and the reproduction check |
| `docs/deployment.md` | Local and Docker serving instructions; no hosted URL unless one is verified |

## Checks

Tests for errors that would silently change results or let bad input through:

- Price files: a missing or third price column, the same ticker twice,
  `2025/01/02`, a repeated or decreasing date, an empty cell, `abc`, `nan`,
  `inf`, 0, a negative price, 10,001 rows, and a file over 1 MB are each
  rejected with a message naming the problem. A file with a byte-order mark
  is accepted.
- Windows: 503 fitting sessions or 19 later sessions are rejected. The fit end
  need not be a session. A 2025-12-31 fit end on the project's prices gives a
  normalization window of 2025-01-02 to 2025-12-31 with 250 sessions. A
  2024-02-29 fit end starts the window after 2023-02-28.
- Normalization: residuals `[1, 2, 3]` give mean 2 and standard deviation 1,
  and 4 maps to Z = 2. A constant window is rejected.
- Verdicts: with fixed seeds, a series built as `0.5 + 0.8 * x` plus AR(1)
  noise (coefficient 0.5) on a random walk `x` passes, and two independent
  random walks fail. Directional p-values of 0.03 and 0.2 give an adjusted 0.06
  and fail, even though 0.03 is below 0.05.
- Failing pair: the response holds test results only. With the exploratory
  option it also holds the spread, Z-scores, and signals, labelled exploratory.
- Signals: the Z path -1.9, -2.1, -2.5, -0.1, 0.0, 2.1 gives a long entry at
  -2.1, holds until the exit at 0.0, then a short entry at 2.1. The first
  session after the fit end is compared with the last fitting Z-score.
- Fit-window isolation: changing prices after the fit end leaves the test
  results, regression, and normalization unchanged.
- Forecasts: 38 sessions, a missing session, an origin after 2026-07-31, and a
  pair without a bundle are rejected. A bundle whose `model.pt` hash changed
  fails its startup check, and `/health` reports it.

The reproduction check uses the project's prices and a 2025-12-31 fit end:

- AMZN_META passes, with a direction-adjusted p of 0.0284 and a trace
  statistic of 17.60 against 15.49. NVDA_AMZN fails.
- For both pairs, the kept direction matches Phase 3. The intercept and beta
  match the Phase 3 artifacts, and the mean and standard deviation match the
  Phase 4 artifacts, within `rtol=1e-7` and `atol=1e-9`. NVDA_AMZN uses the
  exploratory option.
- The 290 unseen Z-scores match `unseen_zscores.csv` within the same tolerance.
  Each date's crossings, eligible entries, exits, and actions match Phase 4's
  `signals.csv` exactly.
- Each bundle reproduces its `known_inference.json` (origin 2025-12-23, 39
  sessions) within `1e-6`. A forecast at a 2026 origin matches the saved
  `phase5_v2` unseen forecast for that origin.

Before reporting completion, confirm that the files hashed by the Phase 4 and
Phase 5 contracts match their recorded hashes and that Git shows no changes in
`trading/`, `features/`, `models/`, `cointegration/`, or `data/master.py`.
Save the before/after lock comparison. One complete interface flow is checked
by hand for each case (an upload, a sample that passes, a sample that fails,
and the exploratory view), comparing the numbers on screen with the API
response.

Commands as run; the verified forms are in the README
and [deployment](../deployment.md).

```powershell
uv add fastapi uvicorn python-multipart streamlit httpx
uv run --locked python -m unittest discover -s tests -v
uv run --locked uvicorn market_analytics.api.main:app --port 8000
uv run --locked streamlit run app/streamlit_app.py
docker build -t financial-market-analytics-3:phase6 .
docker run --name fma3-phase6-historical financial-market-analytics-3:phase6 python scripts/run_pipeline.py --historical-only
docker run --name fma3-phase6-full financial-market-analytics-3:phase6
docker compose up
```

The reproduction test runs in Docker inside the full-pipeline container, after
the pipeline has written its own Phase 3-5 outputs. There it checks the
container's results rather than the Windows ones.

## Handoff

Submission packaging follows this phase. The archive must include the mounted
folders (`artifacts/lstm/phase5_v2/`, `data/processed/`, and
`outputs/metrics/pair_selection/`) or the compose services will not start,
plus any sentiment outputs that Step 1 adds to the interface. A hosted
deployment, if chosen, needs its own way to supply the saved models and its
own verification.
