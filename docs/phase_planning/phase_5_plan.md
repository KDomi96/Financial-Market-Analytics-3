# Phase 5 plan: LSTM forecasts and strategy comparison

Status: implemented. Local reproduction, notebook execution,
both Docker pipeline modes, and saved-weight reload are verified. Independent
Linux retraining does not meet Windows numeric tolerance; that check remains
unresolved. See [findings](phase_5_analysis.md) and the Phase 5 review/Docker
verification records. The fitting
stages, input/target structure, CPU framework, and day-five entry filter are
adopted, as are change targets, seeded shuffling, and the remaining defaults
below. Decisions and
their reasons are in [methodology](../methodology.md#phase-5-lstm-forecasts-and-strategy-comparison).

Phase 5 forecasts each shortlisted spread, measures whether those forecasts
improve on persistence, and compares a forecast-filtered strategy with the
statistical baseline. Forecast accuracy and trading performance answer
different questions. A model that loses to persistence, rejects every entry,
or produces worse returns is still a result to report.

## Inputs and scope

Preserve the two exploratory pairs and their saved directions:

| Pair ID | Direction | Final-fit inputs |
| --- | --- | --- |
| AMZN_META | AMZN on META | `artifacts/statistical/phase3_v1/AMZN_META/ols_20180102_20251231.json` and `artifacts/statistical/phase4_v1/AMZN_META/normalization_2025.json` |
| NVDA_AMZN | AMZN on NVDA | Corresponding JSONs under `NVDA_AMZN` |

Use `data/processed/master_historical.csv`, its manifest entry, the Phase 3
shortlist/metadata, and the Phase 4 configuration and evaluation contract.
Check direction, fit dates, hashes, and residual reconstruction. The final
historical Z-scores must reproduce
`data/processed/statistical_baseline/historical_zscores.csv`.

Only evaluation opens `data/processed/master_unseen.csv`. Phase 4's saved
unseen ledgers remain the full-period reference; they are not inputs to model
or rule selection. Its completion checklist and review/Docker records report
successful verification. Those runs have not been repeated for this plan.

The standalone runner consumes saved inputs; it neither downloads prices nor
reruns earlier phases. The ordered pipeline will add Phase 5 after Phase 4.
Sentiment, VIX, calendar variables, additional pairs, API routes, and the web
interface are outside this phase. Save inference artifacts that the later API
can load without fitting anything.

## Design

| Area | Planned treatment | Status |
| --- | --- | --- |
| Selection fit | Refit the fixed pair directions on 2018-2023; normalize with 2023 residuals; validate on 2024-2025 | Adopted |
| Final fit | Load Phase 3 OLS and Phase 4 normalization; train from scratch through 2025 for the selected epoch count | Adopted |
| Daily features | Z, lags 1/2/3, trailing standard deviation, in that order | Adopted structure |
| Rolling feature | 20 sessions, including the current close, `ddof=1`, all 20 observations required | Adopted |
| Scaling | Standardize each feature from unique training input rows; leave the change targets unscaled in Z units | Adopted |
| Targets | Five changes `Z(t+h) - Z(t)`; forecast is `Z(t)` plus the predicted change | Adopted |
| Batch order | Shuffle training windows each epoch with a generator seeded by the trial seed | Adopted |
| Network | Separate one-layer, unidirectional LSTM for each pair, with five direct outputs | Adopted |
| Experiment budget | Four configurations per pair; two additional seed checks for the selected configuration | Adopted |
| Forecast reference | Persistence on exactly the same origins and target dates | Adopted |
| Trading | Day-five forecast filters fresh entries; observed-Z exits remain unchanged | Adopted |
| Comparison dates | Same entry-eligible origins for both strategies; keep accounting through the period endpoint | Adopted |

The shortlisted pairs and directions were selected using 2018-2025. Earlier
OLS/preprocessing fits prevent validation observations entering those fitted
objects, but do not undo shortlist selection. Describe validation as
conditional on that shortlist. The 2026 period has already been examined in
Phase 4; it is held out from Phase 5 fitting, not a newly untouched dataset.

### Dates and sequence construction

At an origin after close t, the input has shape `(20, 5)` and covers feature
rows t-19 through t. The target has shape `(5,)` and contains the change in Z
from t to each of the next five trading sessions. Each daily rolling feature needs another 19 preceding
Z observations, so a complete input requires 39 consecutive spread
observations through t. Do not pad the beginning, use centered windows, or
fill missing observations.

Assign samples by their target dates. Every training target must end by the
training cutoff. Every validation or unseen target must lie wholly inside
its evaluation period. Earlier dates may provide input context, as already
adopted; overlapping known inputs do not require an extra embargo. Dates in
the saved sample index must demonstrate that training and validation targets
do not overlap.

The following counts were calculated from the historical master's Date column
only. They assume the 20-session rolling feature and no missing rows;
assert them when building the real samples.

| Samples per pair | First origin | Last origin | Complete samples |
| --- | --- | --- | --- |
| Selection training | 2018-02-27 | 2023-12-21 | 1,466 |
| Historical validation | 2023-12-29 | 2025-12-23 | 498 |
| Final training | 2018-02-27 | 2025-12-23 | 1,968 |

Validation has 502 target sessions, starting 2024-01-02. The first validation
origin uses only information available by the final 2023 close. The recorded
145-session unseen period implies 141 complete forecast origins when
2025-12-31 is included. Verify its calendar and exact last origin during
evaluation; this planning check did not open unseen prices.

Save pair, direction, stage, split, input start/end, origin, and all five
target dates with every sample. Include excluded boundary origins and their
reasons in a separate audit. A date must never be inferred from a tensor row
number after splitting.

### Comparable trading periods

Use the adopted filter exactly as defined in methodology: a long entry needs
`forecast_z_h5 > current_z`; a short entry needs `forecast_z_h5 < current_z`.
Equality rejects the entry. This is a direction test, not a promise that the
endpoint is closer to zero or that the trade will make money.

For the primary comparison, both accounts start flat on the first
evaluation session, with the preceding historical Z as crossing context and
no pending order. The preceding-year forecast is scored but cannot create a
carried entry. New entries are eligible only on evaluation-period origins
with complete five-day targets. This schedule is determined by session dates,
never by target values. With the recorded unseen calendar, it gives 140
entry-eligible origins per pair.

Continue observed-Z exits, fills, and daily valuation through the final close,
including the tail without forecast-eligible entries. Never let a missing
tail forecast prevent an exit. Mark any open trade at the endpoint, as in
Phase 4. Retain the original full-period baseline beside the matched baseline
and filtered strategy; do not silently replace it with the restricted run.

Run the baseline and filtered strategy independently through the same engine.
Their holdings can diverge after a rejected entry, so filtering the baseline's
saved trade list would be wrong. A rejected crossing expires; it cannot turn
into an entry on a later outside-band day without a fresh crossing. Compare
each pair separately with the same USD 10,000, sizing, fees, and definitions.
Do not pool the two accounts into a diversified portfolio claim.

## Steps

**1. Freeze the historical experiment settings.** Record the reviewed defaults
in `configs/lstm_forecast.json` before training. Include the full candidate
list, seeds, selection metric and tie rule, preprocessing, periods, accounting
reference, entry-eligibility policy, tolerances, and version. Add CPU-only
`torch` through uv with an explicit package index, following the
[uv PyTorch guide](https://docs.astral.sh/uv/guides/integration/pytorch/).
Lock a build compatible with Python 3.12 on Windows and Linux. Do not add
torchvision, a backtesting framework, or a separate experiment service.

Before going further, confirm that `uv.lock` still resolves numpy 2.5.4,
pandas 3.0.6, and matplotlib 3.11.2. The Phase 4 normalization artifacts
record those versions, and its runner rejects a saved artifact when they
differ ([baseline.py](../../src/market_analytics/trading/baseline.py)), which
would also stop the ordered pipeline. If torch forces a different version,
stop and decide how to preserve the Phase 4 run before training anything.

**2. Prepare the earlier fit and dated features.** Validate the historical
handoff. Fit only the fixed OLS directions on 2018-2023 and save those new
coefficients under Phase 5. Fit mean/sample standard deviation on their 2023
residuals, then apply both objects unchanged to validation prices. Require
finite coefficients and a positive beta for the existing accounting engine;
otherwise stop for a recorded methodological decision rather than switching
direction or taking the beta's absolute value. The current
Phase 4 `fit_normalization` deliberately accepts 2025 only: do not weaken it
to make this work. Use a separate function with explicit fit dates. Reuse
residual application and path/hash helpers where their contracts fit.

Save each stage's resting level in Z units, `-mean / std` from that stage's
last-year normalization. The OLS residuals average zero over their fit
window, but Z is centred on the final year, so the level the spread has
historically returned to is not Z = 0. A planning check on the historical
master gave about 1.07 (AMZN_META) and 2.78 (NVDA_AMZN) for the selection
stage, and 0.57 and -0.47 for the final stage. NVDA_AMZN's selection-stage
level is above the +2 short threshold, so a model that reverts toward it
would tend to reject validation shorts for a reason the final stage does not
share. Report these levels beside the validation filter decisions. They
describe the setup and change no rule. The same check gave positive
selection-stage betas of 0.7265 and 0.2523; confirm them when the fit is saved.

Explore features and boundary samples in `notebooks/05_lstm_comparison.ipynb`,
then move the stable functions into the feature package. Fit the input scaler
on the distinct dates present in training inputs, not on flattened overlapping
sequences. Save those dates/counts and each column's mean/scale. The expected
counts are 1,485 selection-fit rows and 1,987 final-fit rows. Later-period
prices cannot affect earlier OLS, normalization, scaling, or training arrays.

**3. Establish forecast measurements.** Build persistence forecasts and
independently check MAE/RMSE on a tiny example before training. Keep one row per
pair/origin/horizon/target date. The primary selection score is pooled RMSE
over all five horizons for one pair. Save per-horizon MAE/RMSE, pooled MAE/RMSE,
origin counts, prediction counts, and unique target-date counts. Do not
average five RMSE values and call that pooled RMSE.

**4. Select the LSTM on historical data.** Train the four
configurations and retain their histories, best checkpoints, and failures.
Shuffle training windows with the seeded generator, keep validation in date
order, and reset recurrent state for each sequence. Only
2024-2025 forecast error selects a configuration and epoch. Restore the best
checkpoint, produce validation forecasts, then run the two seed sensitivity
checks without changing the selected design or choosing the luckiest seed.
Show persistence alongside every trial. No extra search is triggered merely
because the model underperforms it.

**5. Check the trading adapter on synthetic data and validation.** Reuse
`trading.backtest.simulate` and `trading.signals.decide_signal`. The existing
callback lacks a date argument. Add a factory in `trading/forecast_filter.py`
that binds ordered session dates, current/previous Z, the permitted entry
calendar, and forecasts to that callback. Each invocation consumes exactly
one date, asserts its Z context, and returns the usual signal fields plus
forecast/filter fields. It must not hold future prices or realized targets.
Check its call count against the resulting daily account, including early
termination. Never use the Z value itself as a date lookup key.

This leaves the Phase 4 engine and its code-hash contract intact. A factory
option with no forecast filter supplies the matched baseline's entry-date
mask. Always evaluate observed-Z exits before applying entry restrictions.
Distinguish raw crossings, state-eligible entries, calendar exclusions,
filter acceptances/rejections, submitted orders, fills, and closed/open trades.
Keep the engine's `eligible_long`/`eligible_short` fields as pre-filter
state eligibility and add separate acceptance fields. The comparison summary
must report both rather than relabeling one as the other.
Reconcile both validation ledgers independently. Validation backtests are
diagnostics for the fixed filter, not another optimization target.

Validation trades use the beta from the 2018-2023 selection OLS. The Phase 3
full-history beta (0.5994 and 0.2396) was fitted partly on 2024-2025, so
sizing validation trades with it would leak. Check that validation share
quantities reproduce from the saved selection-stage coefficients.

Save direction diagnostics beside the validation ledgers. Pooled RMSE does
not show whether the sign of `forecast_z_h5 - Z_t` is right, and the filter
uses nothing else. In the selection training data, the mean five-session Z
change after Z > 2 was about -0.10 (AMZN_META) and -0.04 (NVDA_AMZN), while
the standard deviation of five-session changes was 0.60 and 0.48, so the
filter acts on a small expected move. For each pair, report:

- the share of origins where the predicted h5 direction matches the realized
  five-session change, overall and at crossing origins;
- every validation crossing with its Z, h5 forecast, predicted change,
  resting level, and decision;
- how many of those decisions the seed-7 and seed-2026 checkpoints share
  with seed 42.

These are reported, not used to choose a model, seed, epoch, or rule. If the
seeds often disagree, the filter decisions are mostly training noise, and the
findings should say so.

**6. Refit and freeze the final artifacts.** Load and verify the existing
full-history OLS and 2025 normalization, then rebuild all final features and
refit the feature scaler. Initialize a fresh network with seed 42 and train
for the selected configuration's best epoch count. Do not continue from the
selection checkpoint or use an unseen loss for stopping. Save weights,
architecture, preprocessing, selection record, and a known inference example.
Reload the complete bundle and reproduce its five outputs in evaluation mode.

Create an evaluation contract containing input, code, config, lockfile, and
artifact hashes before the Phase 5 evaluator opens unseen data. The bundle
must be usable from price history alone; inference cannot require targets.

**7. Evaluate the frozen models.** Apply the final objects to January-July
2026 without fitting or updating them. Known earlier 2026 closes can supply
later input windows; future closes cannot. Write forecasts before joining
their realized targets for scoring. Run the matched baseline and filtered
strategy through the same engine, retain the full-period Phase 4 reference,
and produce comparison tables from reconciled ledgers. Record boundary
exclusions and final open trades rather than silently dropping them.

**8. Reproduce the run.** Execute the notebook top to bottom, reproduce its
results through the script, inspect figures, and run historical-only and full
pipelines in Docker. Back up generated outputs before any rerun that could
replace them; compare hashes afterward. Historical-only mode must select and
refit without reading unseen masters, prices, forecasts, or backtests.
Evaluation-only mode must load artifacts and never train.

Keep Phase 4's evaluated files unchanged. Its runner rejects changed inputs,
versions, or code under an existing contract. If dependency resolution changes
an earlier recorded runtime, preserve the earlier run and reproduce it in a
separate version/location; do not bypass its contract to extend the pipeline.

**9. Write findings and completion evidence.** Write `phase_5_analysis.md`
from saved outputs. Explain forecasting results, persistence comparison, seed
sensitivity, conditional validation, signal/trade differences, costs, net
exposure, and open P&L. Append actual runs to the experiment log, including
unsuccessful trials. Update the data dictionary, verified README commands,
directory guide, and local completion checklist after their evidence exists.

## Files

These files are implemented. The final notebook imports the shared code.

| File | Responsibility |
| --- | --- |
| `configs/lstm_forecast.json` | Frozen experiments, features, periods, comparison policy, paths, and tolerances |
| `notebooks/05_lstm_comparison.ipynb` | Feature/window exploration followed by imported training, forecasts, and interpretation |
| `src/market_analytics/features/sequences.py` | Earlier-fit OLS/normalization, trailing features, scaler fit/apply, dated windows and exclusions |
| `src/market_analytics/models/lstm.py` | Network, deterministic training, checkpoint save/load, five-step inference |
| `src/market_analytics/models/forecasting.py` | Handoff checks, stages, selection, persistence, metrics, comparison orchestration, metadata |
| `src/market_analytics/models/plots.py` | Loss curves, forecast comparisons, errors by horizon, equity and drawdown |
| `src/market_analytics/trading/forecast_filter.py` | Dated callback adapter, entry calendar, day-five filter, decision audit |
| Feature/model package `__init__.py` files | Package markers where absent |
| `scripts/run_lstm_forecast.py` | Thin offline runner with selection, refit, evaluation, and historical-only modes |
| `scripts/run_pipeline.py` | Add Phase 5 after the existing stages and preserve historical-only isolation |
| `tests/test_lstm_sequences.py` | Feature values, scaler fit rows, chronology, split boundaries, isolation |
| `tests/test_lstm_forecast.py` | Selection rule, metrics, checkpoint reload, stage isolation, small training smoke check |
| `tests/test_forecast_filter.py` | Known filter decisions, date alignment, independent state, counts, accounting equivalence |
| `pyproject.toml`, `uv.lock` | CPU-only torch dependency and resolved Windows/Linux builds |
| `.dockerignore`, `.gitattributes` | Exclude generated Phase 5 objects from builds; preserve saved CSV/artifact bytes |

The small calculation interfaces are `build_features(z, rolling_window)`,
`fit_feature_scaler(training_rows)`, `apply_feature_scaler(features, scaler)`,
and `build_sequences(features, z, target_start, target_end)`. The latter
returns X `(N,20,5)`, the change targets y `(N,5)`, the origin Z values, and
the dated sample index. Keep a separate
`build_inference_inputs` path that needs no y or future prices. Training
returns a checkpoint, epoch history, and selected epoch. Prediction returns
five Z values per ordered origin. Calculations accept explicit arrays/tables;
only orchestration reads files. The stage runner returns metadata in the same
style as the earlier phase runners.

| Saved location | Contents |
| --- | --- |
| `data/processed/lstm/phase5_v1/{selection,final}/` | `features.csv`, `sample_index.csv`, `excluded_samples.csv`; tensors can be rebuilt from these |
| `artifacts/statistical/phase5_v1/selection/<PAIR_ID>/` | `ols_20180102_20231229.json`, `normalization_2023.json` |
| `artifacts/preprocessing/phase5_v1/{selection,final}/<PAIR_ID>/` | Feature means/scales, order, fit dates/counts, parent artifact hashes |
| `artifacts/lstm/phase5_v1/<PAIR_ID>/selection/<TRIAL_ID>/` | `model.pt` state dictionary and metadata for each trial/check |
| `artifacts/lstm/phase5_v1/<PAIR_ID>/final_20180102_20251231/` | `model.pt`, metadata, artifact references/hashes, known inference input/output |
| `outputs/predictions/lstm/phase5_v1/{validation,unseen}/forecasts.csv` | Pair/direction, model/trial, origin, horizon, target date, actual Z, forecast Z, persistence Z |
| `outputs/metrics/lstm/phase5_v1/` | `trials.csv`, `epoch_history.csv`, `selection.json`, `forecast_metrics.csv`, `direction_diagnostics.csv`, `filter_decisions.csv`, `strategy_comparison.csv`, `split_audit.csv`, `run_metadata.json`, `evaluation_contract.json` |
| `outputs/backtests/lstm_comparison/phase5_v1/{validation,unseen}/{baseline_matched,lstm_filtered}/` | `signals.csv`, `executions.csv`, `trades.csv`, `daily_account.csv`, `summary.csv` with pair/run identifiers |
| `outputs/figures/lstm/phase5_v1/` | Learning curves, per-horizon errors, dated h1/h5 forecasts, matched equity/drawdown, accepted/rejected entries |
| `outputs/metrics/phase5_review_validation.json` | Independent checks, tests, notebook execution, artifact reload, chronology and preservation audit |
| `outputs/metrics/phase5_docker_validation.json` | Environment details, reproduction checks, numerical differences, decision agreement |
| `docs/phase_planning/phase_5_analysis.md` | Findings and limitations written after evaluation |

All tables carry pair, direction, exploratory label, stage, and model/run
identity directly or through an unambiguous linked manifest. Never mix
selection-stage and final-stage Z values: they have different fitted scales.
There is no new raw acquisition or useful interim cleaning checkpoint here.

## Checks

Use targeted examples for errors that could silently change the comparison:

- For a synthetic Z series 0, 1, 2, ... the first full feature row is at
  position 19, the first complete origin at 38, and its targets at 39-43.
  Verify lag order, all rolling inputs, `ddof=1`, tensor shapes, and dates.
- A target at cutoff+1 removes the whole training sample. Validation may use
  earlier input context but all its targets follow the cutoff. Changing
  post-cutoff prices cannot change training arrays or fitted preprocessing.
- Fit scaling from unique input dates, with no repeated weighting from
  overlapping windows. Constant columns use scale 1 and record that status;
  non-finite values, missing sessions, insufficient context, and zero residual
  normalization variance fail explicitly. Never clamp later Z values.
- Wrong pair/direction, swapped feature order, stale hashes, mismatched
  normalization, and a model with the wrong input/output shape are rejected.
  Known inputs reproduce after reloading the entire artifact bundle.
- Given controlled validation losses, select the specified checkpoint,
  patience endpoint, and tie winner. A fresh final fit receives only the
  saved epoch count and historical data. A zero predicted change reproduces
  persistence exactly, and saved forecasts equal origin Z plus the predicted
  change. The same seed gives the same batch order. A tiny synthetic training run
  produces finite weights and five outputs without asserting market skill.
- Check persistence, per-horizon and pooled MAE/RMSE by hand, including a
  zero-error benchmark and repeated target dates at different horizons.
- With a fresh long crossing to Z=-2.2, h5=-1.5 accepts, h5=-2.2 rejects,
  and h5=-2.5 rejects. Mirror the short case. Exits work even with no forecast;
  missing forecasts on otherwise eligible origins are errors, not silent skips.
- A rejected crossing followed by several days below -2 creates no delayed
  entry. After holdings diverge, each strategy uses its own position state.
  Repeated identical Z values on different dates still retrieve the right
  forecast. Test callback exhaustion and a nonpositive-equity early stop.
- The last historical origin can be scored but cannot submit an evaluation
  order. Both strategies reject tail entries outside the common calendar and
  keep exits/marks. A missing or reordered forecast key fails before trading.
- Validation share quantities reproduce from the selection-stage beta; a
  ledger sized with the full-history beta fails the check. The saved resting
  levels equal `-mean / std` of each stage's normalization artifact.
- An always-accept filter with the same entry calendar reproduces the matched
  baseline exactly. With unrestricted entry dates it reproduces Phase 4.
  Reuse its hand-computed two-leg P&L example, then independently rebuild
  equity from fills, costs, and price changes for both real comparison runs.
- Changing future prices changes future targets/marks, not earlier forecasts
  or signals. Historical-only mode succeeds with unseen inputs absent;
  evaluation succeeds with training functions patched to raise if called.
  Input/Phase 3/Phase 4 artifact hashes remain unchanged after the run.

For real data, reconcile sample counts and every origin/target date, forecast
counts, signal decisions, fill dates, trade state, costs, and daily equity.
Report the fitted-object audit for shortlist/direction, earlier OLS,
normalization, input scaler, model selection, final refit, and fixed rule.
Record actual date ranges rather than relying on names such as "train".

Use NumPy/pandas checks and the existing unittest suite. The commands below
are the implemented interfaces; the full runner, historical-only mode,
evaluation-only mode, notebook, and both pipelines have been exercised:

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/run_lstm_forecast.py --stage select
uv run --locked python scripts/run_lstm_forecast.py --stage refit
uv run --locked python scripts/run_lstm_forecast.py --stage evaluate
uv run --locked python scripts/run_lstm_forecast.py --historical-only
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/05_lstm_comparison.ipynb
uv run --locked python scripts/run_pipeline.py --historical-only
uv run --locked python scripts/run_pipeline.py
```

The default standalone mode runs select, refit, then evaluate in order.
`--historical-only` runs select and refit; it is mutually exclusive with
`--stage`. Refit requires a saved selection record. Evaluation requires the
frozen final bundle and matching contract. Use the README's workstation uv
and cache setup; add these commands there only after execution verifies them.

## Reproduction and handoff

Exclude Phase 5 processed data, outputs, weights, and preprocessing from the
Docker build context so both pipeline modes build them from permitted pinned
raw inputs. Keep a separate reload test that copies the saved final bundle
into a container and compares inference on the same known inputs.

Fix CPU seeds, deterministic operations, batch order, and thread counts.
Repeat a run in the same environment before comparing Windows with Docker.
[PyTorch does not promise identical training across platforms](https://docs.pytorch.org/docs/stable/notes/randomness.html); distinguish
retraining agreement from inference using identical weights. The
float32 inference tolerances are `rtol=1e-5`, `atol=1e-6`; deterministic
float64 preparation/accounting retain `rtol=1e-7`, `atol=1e-9`. Require exact
date keys, sample membership, selected configuration/epoch, and trading
decisions when claiming complete cross-platform reproduction. If retraining
changes them, save the differences and leave that check unresolved rather
than widening tolerances after seeing results. Use one declared CPU runtime
for the reported final artifact and document any change before evaluation.

The later API should load weights, preprocessing, OLS/normalization, feature
order, and configuration from the saved bundle. It should accept sufficient
dated price history, construct the same inputs, and return five forecasts
without training. Route design, serving commands, sentiment, and submission
packaging remain separate work.
