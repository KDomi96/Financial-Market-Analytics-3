# Phase 4 plan: statistical baseline

Status: implemented and verified 1 November 2026. Results are in the
[Phase 4 analysis](phase_4_analysis.md). The rules
and their reasons are in
[methodology](../methodology.md#phase-4-statistical-baseline).

Phase 4 reconstructs the two shortlisted spreads, fixes their normalization,
and follows each signal through both stock legs to cash P&L. It ends with
dated outputs that Phase 5 can use for a like-for-like strategy comparison.
A lack of reversion, no completed trades, or a loss is a valid result.

## Inputs

Use the saved Phase 3 shortlist and fitted JSONs, preserving pair identity and
regression direction separately:

| Pair ID | Spread column | Coefficient artifact |
| --- | --- | --- |
| AMZN_META | AMZN_on_META | `artifacts/statistical/phase3_v1/AMZN_META/ols_20180102_20251231.json` |
| NVDA_AMZN | AMZN_on_NVDA | `artifacts/statistical/phase3_v1/NVDA_AMZN/ols_20180102_20251231.json` |

Both are exploratory. The [Phase 3 analysis](phase_3_analysis.md) explains
their weak evidence and shared AMZN leg. Load full-precision coefficients;
do not copy the rounded equations from the analysis or refit either direction.

The historical inputs are `data/processed/master_historical.csv`, its entry
in `master_manifest.json`, `data/processed/pair_spreads_historical.csv`, and
`outputs/metrics/pair_selection/{shortlist.csv,run_metadata.json}`. The master
contains 2,011 sessions from 2018-01-02 through 2025-12-31. Read Date and the
AMZN, META, and NVDA Open/Close columns. Check reconstructed historical spreads
against the saved oriented columns before fitting normalization on 2025 rows.

Only the evaluation stage reads `data/processed/master_unseen.csv` and checks
its manifest entry. Its recorded coverage is 145 sessions in January-July
2026. Verify the actual first/last sessions and row count at execution. The
standalone Phase 4 script must not acquire data or rebuild an earlier phase.
S&P 500, VIX, AdjClose, volume, sentiment, and LSTM features are outside these
calculations.

## Adopted decisions

The detailed definitions are in methodology.

| Decision | Adopted rule | Main consequence |
| --- | --- | --- |
| Normalization | 2025 residual mean and sample standard deviation, `ddof=1` | One fixed scale for every unseen observation |
| Entry | Fresh crossings of -2/+2 while flat | Staying outside a band does not generate repeated entries |
| Initial state | Flat; last 2025 Z-score is comparison context only | No carried December position or order |
| Exit | Zero crossing in the trade's direction; exit takes priority | No immediate reversal, stop-loss, or time stop |
| Capital | Separate USD 10,000 accounts; entry budget capped at initial capital and current equity, with entry costs reserved | No pooled AMZN exposure or reinvestment of gains |
| Holdings and costs | Entry-time beta-weighted notionals converted to fixed shares; 5 bps of turnover charged on each fill | Cash P&L and costs can be reconstructed from prices and quantities; net dollar exposure of about USD 2,500 and 6,100 means shared moves affect P&L; net exposure and leg P&L are saved |
| Signal count | Eligible entry signals (crossings while flat), long and short | Raw crossings and outside-band days are reported alongside |
| Endpoint | Mark open trades at the final Close and show them separately | Account returns include unrealized P&L; win rate uses closed trades only |
| Historical exercise | Full 2018-2025 replay with the final fitted parameters, labelled in-sample | Checks the engine without claiming independent validation |

The dollar capital and cost rate are modeling assumptions. They are not
estimates of a broker account's buying power or actual transaction charges.
No result-driven threshold search or expansion of the shortlist is planned.

## Analysis and saved evidence

| Work | Saved evidence |
| --- | --- |
| Reconstruct and normalize | Two reloadable normalization artifacts, exact fit dates/counts, source hashes, historical and unseen spread/Z-score rows |
| Describe spread behaviour | Outside-band frequencies, longest runs, and dated reversion/censoring records; Z-score panels with entry/exit levels |
| Follow signals | Every date's raw conditions, crossings, position state, eligible signals, ignored reasons, pending orders, and execution dates |
| Account for trades | Stock-leg fills and costs, paired trade ledger, daily shares/cash/leg and net exposure, each leg's P&L, gross and net equity/P&L |
| Compare results | Separate pair summaries for historical in-sample and unseen runs, with defined denominators and missing-metric statuses |
| Reproduce and explain | Run metadata, independent reconciliation, notebook, figures, findings, and Docker comparison |

Keep historical and unseen output directories separate. Every table contains
pair ID, direction, evidence label, and run/period identifiers or has those
fields in its linked metadata. Figures show the exploratory label explicitly.

## Steps

**1. Freeze the settings in config.** Create `configs/statistical_baseline.json`
from the adopted decisions before running any real backtest.
Include input/artifact paths, period boundaries, normalization convention,
thresholds, first-session policy, capital, cost rate, endpoint policy, numeric
tolerances, and output version. Keep a settings snapshot with each run.
Run metadata must include that snapshot, input/config/code/artifact hashes,
library versions, actual date windows, validation results, warnings, and the
output inventory with hashes. Version any corrected evaluated run separately.
Do not open unseen prices to decide any of these settings.

**2. Validate the historical handoff.** Check historical and Phase 3 output
hashes, shortlist membership, artifact version, fitting dates, transformation,
direction, finite coefficients, and positive beta. Require unique increasing
dates and finite positive Open/Close values. Compare the saved spread with
`log(dependent_Close) - intercept - beta * log(independent_Close)`. Fail on a
mismatch, missing session, or incompatible artifact; do not silently refit,
fill prices, or infer direction from the pair ID.

**3. Explore normalization in the notebook.** Select only 2025 residual rows,
calculate mean and sample standard deviation, and save both fitted objects.
Reload them and reproduce known Z-scores. Show the historical residuals and
2025 fit window so a narrow recent scale is visible. This fit stage must work
with the unseen master absent. Preserve the Phase 3 artifacts unchanged.

**4. Build and verify the trading engine on small examples.** Implement the
crossing and position rules, a pending next-session order, fixed stock-leg
shares, cash updates, costs, and close marks. Process each session as pending
fill at Open, valuation at Close, then new signal. Save all three stages.
Use the known calculations below before inspecting any real backtest. Keep
signal generation separate from the accounting function so Phase 5 can reuse
the same execution and accounting conventions.

**5. Run the historical exercise.** Apply the final OLS/2025 normalization
throughout 2018-2025, starting flat. Save the full ledger and label all results
in-sample. Check both stock legs and the cash/equity identity on actual trades.
Do not report this as a walk-forward test: the fitted objects use later data
within that period. Fix implementation errors and record the reason for each
changed setting before advancing.

**6. Evaluate unseen data once the checks pass.** Freeze code/settings/artifact
hashes, then validate the unseen master and apply the saved objects without
fitting. Carry only the final historical Z-score as crossing context, with
flat position and no pending order. Use the full January-July range. Keep
the final pending order and any open trade visible without reading later
prices. A subsequent correction must preserve and explain the earlier run.

**7. Describe the results.** Plot Z-scores with distinct signal and fill markers,
gross/net equity, and drawdowns. Save outside-band and reversion diagnostics,
including excursions still unresolved at the endpoint. Reconcile the trade
ledger to account returns before interpreting it. Explain whether spread
behaviour supports reversion during this period and how that differs from
the Phase 3 evidence. Report each pair separately, with net exposure and leg
P&L showing how much of a result came from a move both stocks shared. Each
pair may trade only once or twice, or not at all; treat trade-level metrics
as descriptive and do not change thresholds to obtain more trades.

**8. Promote and reproduce.** Explore in `notebooks/04_statistical_baseline.ipynb`,
then move stable calculations into the trading package and import them in the
finished notebook. Add a thin script. Extend the existing ordered pipeline
after pair selection. Its `--historical-only` mode must fit normalization and
run the historical exercise without opening unseen data; the default mode
adds the unseen evaluation. The standalone script uses existing inputs.

**9. Finish the evidence and documentation.** Execute the notebook top to
bottom, rerun the standalone script, check output agreement, inspect figures,
and reproduce both pipeline modes in Docker. Write `phase_4_analysis.md` from
saved results, append the run to the experiment log, and update the data
dictionary, verified README commands, directory guide, and local completion
checklist. Do not write findings or mark completion before those checks exist.

## Files

| File | Responsibility |
| --- | --- |
| `configs/statistical_baseline.json` | Fixed rules, capital/cost assumptions, periods, input paths, output version, and tolerances |
| `notebooks/04_statistical_baseline.ipynb` | Exploration followed by imported calculations, figures, and interpretation |
| `src/market_analytics/trading/baseline.py` | Input/artifact checks, normalization fit/load/apply, orchestration, diagnostics, summaries, and metadata |
| `src/market_analytics/trading/signals.py` | Raw band conditions, crossings, and state-dependent entry/exit decisions |
| `src/market_analytics/trading/backtest.py` | Next-open fills, sizing, costs, stock-leg holdings, cash, equity, and trade ledger |
| `src/market_analytics/trading/plots.py` | Historical/unseen Z-score, equity, and drawdown figures |
| `src/market_analytics/trading/__init__.py` | Package marker |
| `scripts/run_statistical_baseline.py` | Thin offline entry point with `--historical-only` |
| `scripts/run_pipeline.py` | Add Phase 4 after Phase 3 and pass through historical-only mode |
| `tests/test_statistical_baseline.py` | Known normalization, signal, execution, accounting, boundary, and isolation examples |
| `artifacts/statistical/phase4_v1/<PAIR_ID>/normalization_2025.json` | Mean/std, `ddof`, actual dates/count, direction, OLS path/hash, historical hash, config hash, evidence label, and version |
| `data/processed/statistical_baseline/{historical,unseen}_zscores.csv` | Long-form Date/pair/direction/spread/Z-score data with artifact version |
| `outputs/backtests/statistical_baseline/phase4_v1/{historical,unseen}/signals.csv` | Raw conditions/crossings, eligible and ignored decisions, pending-order status and linked trade IDs |
| Same directory: `executions.csv` | One row per executed stock leg, signed share change, Open price, turnover, cost, signal date, and fill date |
| Same directory: `trades.csv` | Paired entry/exit, both quantities, entry gross notional, gross/net P&L and return, holding sessions, and open/closed status |
| Same directory: `daily_account.csv` | Close holdings, both leg exposures, cash, gross/net equity, daily P&L, cumulative costs, and drawdown |
| `outputs/metrics/statistical_baseline/phase4_v1/{historical,unseen}/` | `summary.csv`, `spread_diagnostics.csv`, `reversion_events.csv`, and `run_metadata.json` |
| `outputs/figures/statistical_baseline/phase4_v1/{historical,unseen}/` | Z-score panels, gross/net equity, and drawdown |
| `outputs/metrics/phase4_review_validation.json` | Independent calculations, reconciliation, tests, notebook results, and leakage audit |
| `outputs/metrics/phase4_docker_validation.json` | Docker commands, runtime identifiers, comparisons, and matching discrete decisions |
| `docs/phase_planning/phase_4_analysis.md` | Findings, accounting interpretation, and limitations, written after evaluation |
| `.dockerignore` | Exclude fitted `artifacts/statistical/phase4_v1` so Docker rebuilds normalization |
| `.gitattributes` | Preserve bytes for the new metric and backtest CSV paths |

No raw or interim dataset is needed. Transformed spread rows belong in
processed data, fitted normalization in artifacts, and trading records in
outputs. Use the existing NumPy, pandas, and matplotlib dependencies and
unittest suite; no new backtesting framework is planned.

The shared interfaces should remain small: a historical-only normalization
fit, application of saved parameters to dated prices, a close-time signal
decision from current state, and an engine accepting dated Open/Close prices
and that decision function. `run_statistical_baseline(config_path,
historical_only=False)` returns metadata in the same style as the earlier
phase runners. Only orchestration reads files; calculations accept explicit
data and settings so synthetic tests cannot accidentally load real prices.

## Checks

Use a small set of tests for errors that could silently change results:

- Normalization of residuals `[1, 2, 3]` has mean 2 and sample standard
  deviation 1; applying it to 4 produces Z=2. Zero variance, missing values,
  and insufficient observations fail. Reloading preserves results.
- A swapped direction, wrong artifact hash, 2026 row in the fit input,
  duplicate date, missing session, or invalid Open/Close fails explicitly.
- Values exactly at +/-2 do not enter. Moving from -2 to below -2 enters
  long; moving from +2 to above +2 enters short. Repeated outside-band days
  do not create fresh crossings. Zero triggers the appropriate exit.
- Opposite crossings while held produce the exit only. The ignored crossing
  never becomes a later entry without a fresh crossing. Starting outside a
  band follows the documented boundary rule.
- A Friday close signal fills at the next session's Open. Changing that
  future Open changes shares/fill P&L but not the preceding signal. Changing
  a later Close cannot change earlier signals or fills. Gaps are retained.
- For a long spread with beta 0.5 and leg notional N=100, Opens of 10 and 20
  produce shares +10 and -2.5. Exiting at 11 and 18 gives gross P&L 15.
  Entry turnover is 150 and exit turnover 155; at 5 bps their costs are
  0.075 and 0.0775, leaving net P&L 14.8475. Test the short direction too.
  This accounting fixture sets N directly; test the capital-to-N rule separately.
- Sizing reserves entry fees, shrinks after losses, and stays capped after
  gains. Short-sale proceeds do not create a second allocation. Equity rebuilt
  without the engine, from `executions.csv` and the Open/Close prices, as C
  plus each leg's held shares times its price changes minus cumulative costs,
  matches the engine's daily equity; gross minus net equals costs.
- A final-day signal is counted but unfilled. An open trade contributes its
  marked P&L and incurred costs to equity, has no invented exit cost, and is
  excluded from win rate. No-trade and no-closed-trade summaries are distinct.
- Drawdown includes initial capital, so an immediate loss is not omitted.
  Nonpositive equity produces an incomplete status, not a normal summary.
- Fit/historical mode succeeds with unseen files absent and does not validate
  their hashes. Altering unseen observations cannot change saved coefficients,
  normalization, or the historical output. Evaluation does not call fitting.

For each real pair/run, reconcile execution rows to trades, trades to daily
account P&L, and the daily account to summaries. Check signal counts from raw
rows independently. Require executed entries to equal closed plus open trades;
every executed order has a signal on the preceding trading session. Compute
one trade and one normalization directly from source values without calling
the production wrappers. Save the checks and tolerances.

Record a fitted-object audit with actual dates for Phase 3 selection and OLS,
2025 normalization, and rule selection. Mark the historical replay in-sample
and unseen application fixed. Preserve the inputs and check their hashes
after execution. Repeated local results should agree; compare Windows/Docker
numeric values with `rtol=1e-7`, `atol=1e-9` and matching missing-value masks.
Signals, directions, trade dates, statuses, and counts must match exactly.
Investigate threshold disagreements even if Z-scores are numerically close.

The following commands completed successfully:

```powershell
uv run --locked python scripts/run_statistical_baseline.py --historical-only
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/run_statistical_baseline.py
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/04_statistical_baseline.ipynb
uv run --locked python scripts/run_pipeline.py --historical-only
uv run --locked python scripts/run_pipeline.py
```

Use the workstation uv/cache setup already documented in README. For Docker,
rebuild the image and use separate named containers for historical-only and
full runs. Derived data, outputs, and fitted Phase 3/4 objects must be created
inside the container from pinned permitted raw snapshots. Excluding these
files from the image checks that reproduction does not depend on workstation
results. The historical-only container must have no unseen master or Phase 4
unseen outputs. Copy results to a separate comparison directory and record
commands, versions, numeric differences, and exact decision agreement.

Verification: 55 passing tests locally and in Docker, seven executed notebook
code cells without errors, and 16 run checks per period. All 18 distinct
CSV/artifact hashes repeat locally. Both Docker modes completed, with exact
signal/trade decisions and a largest CSV difference of 2.18e-11. Evidence is
in `outputs/metrics/phase4_review_validation.json` and
`outputs/metrics/phase4_docker_validation.json`.

## Handoff to Phase 5

Preserve the Phase 4 configuration, normalization artifacts, and baseline
ledgers. Phase 5 should reuse execution/accounting and compare on common
eligible dates with the same capital, costs, endpoint policy, and metrics.
Keep the full-period Phase 4 result as well as any explicitly matched-window
comparison. Phase 5's historical validation still needs its earlier regression
fit and preprocessing; these full-history Phase 4 artifacts are not valid
substitutes for those training objects. The adopted final Phase 5 refit uses
the same 2025 normalization as Phase 4, so their final Z-scores share a scale.
Phase 5's proposed forecast origins include 2025-12-31 and stop where complete
five-day targets end. Distinguish forecast evaluation from trading eligibility:
any comparison using those origins must apply the same start/end trading rules
to both strategies, rather than giving one an earlier entry opportunity.
