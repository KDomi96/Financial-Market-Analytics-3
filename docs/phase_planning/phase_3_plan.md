# Phase 3 plan: pair selection

Status: implemented and verified, 1 November 2026. Results and limitations are
in the [Phase 3 analysis](phase_3_analysis.md). The
statistical settings and their reasons are in
[methodology](../methodology.md#phase-3-pair-selection).

Phase 3 compares all 15 pairs, keeps both OLS directions, and saves a spread
that can be recreated for each pair. It ends with a ranked comparison
and two pairs to carry forward. Weak evidence is a possible result, and any
such selection stays labelled exploratory.

## Inputs

Use `data/processed/master_historical.csv` only, checked against its historical
output entry in `data/processed/master_manifest.json`. Read Date and the six
Close columns explicitly. The expected coverage is 2,011 sessions from
2018-01-02 to 2025-12-31. Unlike return-based EDA, log-price regressions retain
the first historical session.

Use the existing stock order, MSFT, GOOGL, NVDA, AAPL, AMZN, META, and the same
pair identifiers as EDA, from `MSFT_GOOGL` to `AMZN_META`. Pair identity does
not change when the dependent stock changes; record dependent and independent
symbols separately.

The [Phase 2 analysis](phase_2_analysis.md#what-this-means-for-phase-3) provides
context, including changing return correlations. It does not screen or rank
pairs here. S&P 500, VIX, returns, AdjClose, and calendar indicators are outside
the statistical inputs. No acquisition, master rebuild, or unseen-file check
belongs in the standalone Phase 3 run.

## Analysis and saved evidence

| Work | Saved evidence |
| --- | --- |
| Integration checks | Twelve ADF results: log levels and first differences for six stocks, with terms, lags, dates, and assumption flags |
| Directional relationships | Thirty OLS/Engle-Granger rows with coefficients, test statistics, raw p-values, and residual ADF lag details |
| Johansen comparison | Fifteen results with both rank hypotheses, trace and maximum-eigenvalue statistics, critical values, sequential ranks, and the lag-selection scores |
| Ranking and shortlist | Fifteen ranked pairs with selected direction, method-agreement group, pair-level and Holm-adjusted p-values, and assumption flags; two shortlisted rows with reasons and evidence labels |
| Supporting diagnostics | Half-life estimates for 15 selected-direction spreads and 30 subperiod regressions for hedge-ratio comparison |
| Handoff | Historical spreads for all 15 selected directions, fitted JSON parameters, and metadata linking every output to its input and settings |

Four figure groups cover all 15 pairs: observed and OLS-fitted log prices,
residual histories, the evidence comparison, and subperiod hedge ratios. Split
figures into pages if labels would otherwise be too small. Show units, fitting
dates, direction, and weak-evidence labels where relevant. Historical residuals
are fitted in sample; their appearance is not a backtest.

## Steps

**1. Fix the settings in config.** The
[test design](../methodology.md#test-design-adopted-2026-11-01),
[comparison rules](../methodology.md#comparison-and-shortlist-adopted-2026-11-01), and
[diagnostics](../methodology.md#supporting-diagnostics-adopted-2026-11-01) were
adopted on 1 November 2026. Put them in `configs/pair_selection.json` before
running any real-data test. Changing a setting later needs a reason and
another logged run; preserve the earlier results rather than selecting
whichever version looks best.

**2. Check the input and form the pairs.** Confirm the historical hash, required
columns, unique increasing daily dates, exact coverage, and positive finite
Closes. Stop on missing or invalid prices; do not fill, winsorize, or remove
large-move days. Take natural logs and generate the 15 pairs once. Keep the
master unchanged. Reuse the established path and hashing helpers; do not reuse
the EDA reader, which also requires returns, benchmark, and VIX.

**3. Check integration in the notebook.** Run the twelve specified ADF checks
and save their actual estimation dates, input and effective sample counts,
deterministic terms, lag limits, selected lags, statistics, p-values, and
critical values. Attach the resulting stock assumption flags to every pair.
An unexpected integration result does not remove a pair from the comparison;
it limits how its later tests can be interpreted.

**4. Fit both directions and test their residuals.** Fit an intercept and
log-price slope in each of the 30 directions. Save the intercept, beta,
R-squared as a descriptive fit measure, and regression dates/counts. Run
Engle-Granger with the same intercept convention and explicit lag settings.
Use a matching no-constant residual ADF calculation to recover the selected
lag and effective count, and check its statistic against Engle-Granger.
Only the Engle-Granger p-value is used for cointegration inference, and it,
not the printed critical value, decides rejection.

Any failed fit, non-finite statistic, or collinearity warning stops the run.
Choose each pair's direction by the smaller raw Engle-Granger p-value. Do not
choose by OLS R-squared, residual variance, half-life, or future returns.
Form the pair p-value as twice the smaller directional p-value, capped at 1,
and apply Holm across the 15 pairs. Reconstruct the selected spread from the
saved coefficients and compare it with the OLS residuals before saving it.

**5. Run Johansen for every pair.** Use the canonical two-column order and
the specified constant convention. Save the VAR information-criterion curve,
chosen levels lag, and corresponding number of lagged differences. Record
trace and maximum-eigenvalue results separately, including the sequential
rank decisions at 90%, 95%, and 99%. A rejection of rank zero alone does not
establish rank one. Do not invent Johansen p-values or replace the OLS spread
with a Johansen eigenvector.

**6. Compare evidence and calculate diagnostics.** Rank the pairs by
method-agreement group (both methods, one, or neither), then by the selected
direction's raw Engle-Granger p-value within each group. Show the Holm and
integration flags alongside, so a nominal rejection cannot be mistaken for
stronger evidence. Then estimate spread half-life and refit the
selected direction separately on 2018-2021 and 2022-2025. These are historical
diagnostics; they do not change the ranking or the full-period coefficients.

**7. Record the shortlist and export parameters.** Carry the first two pairs
in the ranking forward, with an explicit reason and evidence label for each.
A selection that lacks the adopted evidence conditions is exploratory,
including when only one of the two qualifies. Do not change test settings to
obtain supported pairs. Flag nonpositive hedge ratios for interpretation
before Phase 4 accounting.

Save the selected-direction parameters for all 15 pairs, with shortlist
membership. A later phase can inspect any pair without silently refitting it.
Each JSON identifies the pair, dependent and independent stocks, natural-log
Close transformation, intercept, beta, actual fitting dates, observation
count, model version, evidence label, input/settings hashes, and relevant
library versions. Use ordinary JSON numbers, never NaN or infinity.

**8. Promote and reproduce.** Explore in `notebooks/03_pair_selection.ipynb`
first, then promote stable calculations and plotting into the cointegration
package. The finished notebook imports those functions. Add a thin offline
script and the small checks below. Extend the batch pipeline after EDA while
retaining its historical-only option. The standalone script reads the saved
historical master; it does not invoke earlier phases.

**9. Write the findings and finish verification.** Execute the notebook from
top to bottom, reproduce the tables through the script, inspect the figures,
and repeat the historical-only pipeline in Docker. Write the analysis from
saved results and append the run to the experiment log. Update the data
dictionary, directory guide, verified README commands, and local completion
evidence.

## Files

The files below are implemented. The executed notebook and standalone script
use the same shared calculations.

| File | Responsibility |
| --- | --- |
| `configs/pair_selection.json` | Historical paths, stock order, statistical settings, shortlist size, tolerances, and output locations |
| `notebooks/03_pair_selection.ipynb` | Exploration, final imported calculations, figures, and explanations |
| `src/market_analytics/cointegration/selection.py` | Historical input checks, tests, diagnostics, ranking, parameter export, and metadata |
| `src/market_analytics/cointegration/plots.py` | Figures from the same calculated data and tables |
| `src/market_analytics/cointegration/__init__.py` | Package marker |
| `scripts/run_pair_selection.py` | Thin command-line entry point |
| `scripts/run_pipeline.py` | Add pair selection after the master build and EDA |
| `tests/test_pair_selection.py` | Numerical, direction, rank, serialization, and historical-isolation checks |
| `.gitattributes` | Add `-text` for `outputs/metrics/pair_selection/*.csv` and `artifacts/statistical/**`; `data/processed/**` already covers the spread CSV |
| `outputs/metrics/pair_selection/integration_tests.csv` | Twelve stock/transformation ADF rows |
| `outputs/metrics/pair_selection/directional_tests.csv` | Thirty directional fits and tests with raw p-values |
| `outputs/metrics/pair_selection/lag_selection.csv` | VAR BIC scores for orders 0-10, with eligibility and selected-order flags: 165 rows on valid real inputs |
| `outputs/metrics/pair_selection/johansen_tests.csv` | Fifteen wide rows containing both rank hypotheses and both test families |
| `outputs/metrics/pair_selection/pair_ranking.csv` | All 15 pairs, selected directions, agreement groups, pair-level and Holm-adjusted p-values, ranking, evidence flags, diagnostics, and shortlist membership |
| `outputs/metrics/pair_selection/shortlist.csv` | Two selected pairs, explicit reasons, and supported/exploratory labels |
| `outputs/metrics/pair_selection/half_life.csv` | Fifteen selected-direction AR(1) diagnostics with estimation counts and statuses |
| `outputs/metrics/pair_selection/hedge_stability.csv` | Two subperiod OLS rows per pair: 30 rows |
| `outputs/metrics/pair_selection/run_metadata.json` | Input, config, code and output hashes; actual dates; conventions; versions; warnings; validation; output inventory |
| `data/processed/pair_spreads_historical.csv` | Date and 15 selected-direction residual columns over 2,011 sessions, named `<dependent>_on_<independent>` (for example `AAPL_on_NVDA`) so orientation is unambiguous |
| `artifacts/statistical/phase3_v1/<PAIR_ID>/ols_20180102_20251231.json` | Selected-direction coefficients and reconstruction metadata for each pair |
| `outputs/figures/pair_selection/` | Fitted-price panels, residual histories, method comparison, and hedge-ratio comparison |
| `docs/phase_planning/phase_3_analysis.md` | Observed results, interpretation, shortlist reasons, disagreement, and limitations; written after the run |

No extra raw or interim dataset is needed. The historical master is already
aligned; logs can be calculated in memory. Spread rows belong in processed
data, fitted coefficients in artifacts, and test/diagnostic tables in outputs.
No 2025 normalization, Z-scores, trading signals, or P&L are produced here.

The existing NumPy, pandas, statsmodels, and matplotlib dependencies cover the
implemented work. No dependency or lock change was needed. Use the current unittest
suite and the uv-managed environment.

## Checks

Use small examples for the calculations that can fail silently:

- Six symbols produce 15 canonical pairs and 30 directions. Reversing a
  regression preserves pair identity and changes its dependent/independent
  fields, and the spread column name puts the dependent stock first.
- An independent least-squares calculation agrees with the fitted intercept,
  beta, and residuals. Loading an exported JSON reproduces the saved spread
  from the original Close values, including the intercept and orientation.
- Residual ADF uses no deterministic term and matches the Engle-Granger
  statistic and chosen lag settings. The exported inferential p-value comes
  from `coint`, not the ordinary residual ADF result.
- A hand-calculated example of the pair p-value, twice the smaller
  directional p-value capped at 1, and its Holm adjustment over 15 pairs
  matches the library result.
- Fabricated Johansen statistics cover rank 0, rank 1, and rank 2, and
  trace/maximum-eigenvalue disagreement. Selection stops at the first
  non-rejection. A trace rank of 2 is not rank-1 support.
- The ranking puts a pair supported by both methods above a one-method pair
  with a smaller Engle-Granger p-value.
- VAR order selection considers eligible orders 1-10 using equal-length
  estimation samples; order zero stays visible but is ineligible. Levels
  order p becomes `k_ar_diff = p - 1`.
- A known AR(1) coefficient of 0.5 gives a half-life of one session.
  Coefficients outside 0 < phi < 1 get an explicit status. Subperiod fits use
  only their stated dates.
- Missing, nonpositive, or non-finite prices, a non-finite test statistic,
  and a collinearity warning each stop the run with an error.
- The run succeeds when only historical market data are available. A 2026
  row supplied as historical input is rejected. The manifest lookup and
  analysis never open the unseen master or raw unseen records.

For the real run, reconcile all table counts above, the 15 spread columns,
2,011 residual dates, and the fitted-parameter inventory. Verify OLS residual
reconstruction independently with `numpy.linalg.lstsq`, rather than calling
the same fitting wrapper twice. Check selected directions, Holm values,
agreement groups, rank decisions, shortlist membership, and cross-file keys
directly from the saved tables. Every p-value lies in [0, 1]. Confirm the
input hash is unchanged.

Numeric tables must reproduce on repeated local runs. Compare Windows and
Docker values with `rtol=1e-7`, `atol=1e-9`, and matching missing-value masks.
Directions, ranks, statuses, and shortlist membership must match exactly.
Investigate a platform-dependent decision near a cutoff rather than hiding it
inside the numeric tolerance. Figure byte equality is not required.

The following commands were exercised with the workstation uv/cache and
Jupyter setup documented in the README:

```powershell
uv run --locked python scripts/run_pair_selection.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/03_pair_selection.ipynb
uv run --locked python scripts/run_pipeline.py --historical-only
```

All commands completed successfully. The full suite has 43 passing tests,
including 12 Phase 3 tests. The notebook executed all five code cells without
errors. All 24 data/table/artifact hashes matched on repeat execution.
Docker and independent numerical checks are recorded in
[`phase3_docker_validation.json`](../../outputs/metrics/phase3_docker_validation.json)
and [`phase3_review_validation.json`](../../outputs/metrics/phase3_review_validation.json).

For Docker, rebuild the existing image and run the extended historical-only
pipeline in a named container. It must rebuild the master from the pinned raw
snapshots, reproduce EDA, and create Phase 3 outputs inside the container.
There must be no unseen master. Copy the new metric tables, spread file, and
fitted JSONs to a separate comparison directory and check them against the
local run. Verify the batch run generates its own parameters without reading
workstation artifacts. Save image/runtime identifiers, commands, counts,
differences, and decision agreement in
`outputs/metrics/phase3_docker_validation.json` after that check succeeds.

## Handoff and documentation

The Phase 3 analysis must explain what the integration checks imply, whether
the two directions agree, how Engle-Granger and Johansen compare, what survives
Holm adjustment, and why the selected pairs are carried forward. Discuss
subperiod instability and the limits of the half-life estimate. Do not infer
tradability or profitability from a stationarity test.

Record a leakage-audit table for the integration/lag choices, pair and direction
selection, full-history coefficients, and diagnostic subperiod fits. Identify
their actual fit dates and intended uses. Phase 4 will load the full-history
coefficients and estimate normalization on 2025 residuals. Phase 5 must refit
the regression on 2018-2023 for its 2024-2025 model validation, as already
[adopted](../methodology.md#fitting-stages-adopted). That validation remains
conditional on a shortlist selected through 2025.

Keep methods and rationale in `methodology.md`, findings in the future
`phase_3_analysis.md`, run records in `experiment_log.md`, and completion
criteria/evidence in the local checklist.
