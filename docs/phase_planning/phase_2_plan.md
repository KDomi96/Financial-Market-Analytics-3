# Phase 2 plan: exploratory analysis

Status: implemented and verified, 25 October 2026; results are in the
[Phase 2 analysis](phase_2_analysis.md). The scope and the detailed methods are
adopted in [methodology](../methodology.md#phase-2-exploratory-analysis):
compare return and risk, examine every stock pair and benchmark sensitivity,
check how relationships change over time, and add VIX context. This plan sets
out the work order, files, and checks.

## Inputs

Use `data/processed/master_historical.csv` only. The completed Phase 1 build
records 2,011 sessions from 2018-01-02 to 2025-12-31. Return-based analyses
have 2,010 observations because the first historical return is missing.

Read Date, the six stocks' Close and Return columns, GSPC_Close, GSPC_Return,
and VIX_Close explicitly. Use MSFT, GOOGL, NVDA, AAPL, AMZN, and META in a fixed
display order. Derive analysis years from Date. AdjClose, volume, and the
other calendar fields are outside the selected inputs.

Check the historical file against its SHA-256 entry in
`data/processed/master_manifest.json`. Read only the historical output entry
for this check; there is no need to open or validate an unseen output. Record
the historical input hash in the EDA run metadata. No acquisition or master
rebuild is part of an EDA run.

## Analysis and saved evidence

| Work | Tables | Figures |
| --- | --- | --- |
| Return and risk | Whole-period and annual summaries for six stocks plus the S&P 500 | Performance indexed to 100; drawdown panels |
| All 15 stock pairs | Daily-return and log-price correlations, with sample counts | Rebased log-price panels and daily-return scatterplots for every pair; return-correlation heatmap |
| S&P 500 sensitivity | Whole-period and annual stock/benchmark regressions | Six stock/benchmark scatterplots with fitted lines |
| Relationship stability | Annual pair correlations and dated 60-session rolling correlations | Pair-by-year heatmap and rolling-correlation panels for all 15 pairs |
| VIX context | Daily stock volatility and all-pair correlations by VIX group, plus group counts by year | Historical VIX timeline with the group boundaries |

The figure groups can span several pages if that makes the labels readable.
Keep symbol order, colours, units, and correlation scales consistent. The
performance chart may use a labelled logarithmic vertical scale if a linear
scale hides differences between the other series. The outputs are saved in
`outputs/metrics/eda/` and `outputs/figures/eda/`.

## Steps

**1. Fix the methods.** Record the reviewed Phase 2 methods as Adopted in the
methodology, with a dated decision-log entry, and put their settings in
`configs/eda.json`. This happens before any calculation on the historical
master, so the window length and VIX rule are on record before their results
exist. A later change needs a recorded reason, and the run metadata's settings
hash shows which version produced each output.

**2. Check the historical input.** Confirm the required columns, unique
increasing dates, expected coverage, positive finite Closes including VIX,
and finite returns except for the seven permitted missing returns on the first date.
Reject an input containing dates outside the historical range. Stop on an
unexpected missing value instead of filling it or quietly dropping dates.
The input master remains unchanged.

**3. Explore return and risk in the notebook.** Build the performance and
drawdown views, then the whole-period and annual summaries using the
[return and risk definitions](../methodology.md#return-and-risk-measures-adopted-2026-10-25).
Record the peak and trough dates of each maximum drawdown with its size.
Check compounding, percentage units, annual boundaries, and the initial
drawdown baseline before interpreting any comparison.

**4. Examine all pairs.** Generate the 15 unordered pairs once, as
combinations taken in the fixed display order, so the list runs from
MSFT-GOOGL to AMZN-META. The first symbol of each pair is the one that comes
earlier in that order, and the pair identifier joins the two in the same
order, for example `MSFT_GOOGL`. Reuse that list and order in every pair
table, heatmap, and panel. Produce the return-correlation matrix,
the pair table, and both sets of relationship panels. Preserve observations
from large-move days. Explain level and return correlations separately.

**5. Estimate benchmark sensitivity.** Fit each of the six return regressions
with an intercept, for the whole period and separately by year. Save the
coefficients and descriptive fit measures before plotting the fitted lines.
Check that beta and correlation agree with independently calculated values.
These coefficients belong in the EDA tables; they are not spread parameters
or inference artifacts.

**6. Examine stability.** Calculate annual correlations and the single
rolling view for every pair. A window whose returns are constant for either
stock gets the zero-variance status when its maximum equals its minimum, an
exact test that a standard deviation of rounded floats is not; the correlation
pandas returns for it (`inf` in pandas 3.0.6) is discarded. Compare those with the whole-period
values and the annual benchmark results. Describe changes without picking a
window or a pair because it looks most favourable. Keep all 15 pairs available
for Phase 3.

**7. Add VIX context.** Plot the historical VIX, then apply the
[grouping method](../methodology.md#vix-context-adopted-2026-10-25)
to dates with valid stock and benchmark returns. Save the group boundaries at
full precision, with their estimation dates, in the run metadata; rounded
values could put a VIX close that sits on a boundary in the wrong group. Calculate the grouped daily
volatility summaries, all 15 pair correlations in each group, and group
counts by year. Interpret these alongside the stability results. Do not
calculate compounded returns over a group's non-consecutive dates or turn
the comparison into a trading filter.

**8. Promote the calculations and rerun.** Once the notebook calculations are
settled, move the reusable calculations and plotting into the analysis
package. The notebook then imports them. Add a thin script that saves the same
tables and figures without requiring an interactive notebook session. Add
small tests for calculations and date handling that could fail silently.
Add the pipeline script, which runs the master build and then the EDA, and
make it the image's default command, as set out under
[Docker runtime](../methodology.md#docker-runtime-adopted-2026-10-25).

**9. Write the findings and verify reproduction.** Execute the notebook from
top to bottom, reproduce its numeric outputs through the script, and inspect
the exported figures. Write `phase_2_analysis.md` from the saved outputs,
including the main comparisons, changing relationships, and limitations.
Check the run in Docker as described under Checks, then update the README
commands and the completion evidence. Planning alone does not change Phase 2's
completion status.

## Files

| File | Responsibility |
| --- | --- |
| `configs/eda.json` | Historical input and manifest paths, stock order, agreed calculation settings, and output directories |
| `notebooks/02_eda.ipynb` | Exploration, final imported calculations, figures, and short explanations |
| `src/market_analytics/analysis/eda.py` | Input checks, summary tables, pair correlations, benchmark regressions, VIX group comparisons, and output writing |
| `src/market_analytics/analysis/eda_plots.py` | Figures made from the same data and tables used by the notebook |
| `src/market_analytics/analysis/__init__.py` | Analysis package marker |
| `scripts/run_eda.py` | Thin entry point for the offline analysis |
| `scripts/run_pipeline.py` | Runs the batch phases in order (master build, then EDA); `--historical-only` passes through to the build |
| `Dockerfile` | Default command changed from the master build to the pipeline script |
| `tests/test_eda.py` | Small numerical examples, annual-boundary checks, pair coverage, VIX group assignment, and historical isolation |
| `outputs/metrics/eda/stock_summary.csv` | Seven whole-period rows, with return/risk measures, maximum-drawdown peak and trough dates, counts, and observation dates |
| `outputs/metrics/eda/stock_annual_summary.csv` | Seven instruments for each of eight years, with the same measures |
| `outputs/metrics/eda/pair_correlations.csv` | Fifteen pairs, return and log-price correlations, separate sample counts, and statuses |
| `outputs/metrics/eda/return_correlation_matrix.csv` | Six-stock daily-return correlation matrix |
| `outputs/metrics/eda/benchmark_sensitivity.csv` | Six stocks for the whole period and each year; alpha, beta, R-squared, correlation, counts, dates, and statuses |
| `outputs/metrics/eda/pair_annual_correlations.csv` | Fifteen pairs for each of eight years, with counts and statuses |
| `outputs/metrics/eda/rolling_correlations.csv` | Window-end date, pair, paired count, correlation, and status, including incomplete windows |
| `outputs/metrics/eda/vix_group_stock_summary.csv` | Three VIX groups for seven instruments; daily-return sample standard deviation, mean absolute daily return, counts, and dates |
| `outputs/metrics/eda/vix_group_pair_correlations.csv` | Three VIX groups for all 15 pairs; daily-return Pearson correlation, counts, dates, and statuses |
| `outputs/metrics/eda/vix_group_year_counts.csv` | Observation counts for every VIX group and historical year, including zero counts |
| `outputs/metrics/eda/run_metadata.json` | Input/settings hashes, date coverage, calculation conventions, VIX group boundaries and estimation dates, library versions, output inventory, and validation results |
| `outputs/figures/eda/` | Exported PNG figures with descriptive filenames |
| `docs/phase_planning/phase_2_analysis.md` | Findings and limitations, with numerical claims linked to saved tables and figures |

Save percentages with names ending in `_pct`; correlations, beta, and
R-squared are dimensionless. Tables retain calculation precision; rounding is
for presentation. Every estimate identifies the observations it uses. A
missing estimate has a status explaining whether the cause is an incomplete
window, insufficient observations, or zero variance. Zero variance is checked
on the input values before an estimate is accepted, because library output
does not mark it reliably.

The added dependencies are NumPy for array/log calculations, matplotlib for
static figures, and statsmodels for the benchmark regressions. They are
declared in `pyproject.toml` and resolved in `uv.lock`. No new processed
master, feature dataset, or trained model is needed for EDA. The final EDA
run gets one entry in `docs/experiment_log.md`, because its tables hold
numbers the report will cite.

## Checks

Use a few small synthetic examples for the numerical risks:

- Percentage returns of +10% and -10% compound to -1%, rather than zero.
  Sample standard deviation and the fixed annualization factor match an
  independent calculation.
- A wealth path includes its initial value when calculating drawdown. A
  first-session loss in a later calendar year is retained, and annual returns
  include that session's return from the previous year's final Close.
- Six symbols produce exactly 15 unordered pairs without reversed duplicates.
  The matrix and pair table agree; identical varying returns correlate at 1,
  opposite returns at -1, and constant samples remain undefined, including
  their diagonal matrix entries. Matching missing values preserve symmetry.
- A made-up stock series equal to an intercept plus twice the benchmark has
  the expected intercept, beta of 2, and R-squared of 1. Constant benchmark
  returns produce an undefined estimate with a status.
- Rolling results start only after the required valid observations. Changing
  a later observation cannot change an earlier window's result. A window with
  constant returns for one stock is missing with the zero-variance status,
  never `inf`. A history shorter than the window has only incomplete rows.
- VIX group assignment handles equality at each boundary and keeps tied
  values together. The first missing-return date is excluded from boundary
  estimation and grouped return statistics. Every eligible date belongs to
  exactly one group; constant or insufficient samples retain an explanatory
  status for estimates that are undefined.
- The run works with only the historical market-data input available. No code
  opens the unseen master, and a 2026 row supplied as historical input is
  rejected.

On the real input, confirm the expected seven summary rows, 56 annual summary
rows, 15 pair rows, 120 annual pair rows, and 54 benchmark rows. Verify matrix
symmetry, matching sample counts, and the simple-regression identities
`beta = covariance(stock, benchmark) / variance(benchmark)` and
`R-squared = correlation ** 2` where defined. Every defined correlation in
every table lies between -1 and 1.

The rolling table keeps the full date/pair grid so missing early windows are
visible: 2,010 return dates for each of 15 pairs, or 30,150 rows. The first 59
dates of each pair, 885 rows in all, have the incomplete-window status, and
the first complete window ends on 2018-03-29. Recalculate a few windows
directly from their 60 paired returns and compare them with the saved values;
pandas computes rolling correlation from running sums, so this is an
independent check.

The VIX comparison adds 21 instrument/group rows, 45 pair/group rows, and 24
group/year count rows. Check that grouped counts reconcile to the same 2,010
return dates, that stock and pair rows use the correct group's dates, and
that the saved boundaries reproduce the assignments. Empty groups retain
their output rows with zero counts and missing estimates. VIX is aligned by
Date; it is never independently sorted or shifted onto another return date.

Check that whole-period and annual compounded returns match the corresponding
Close ratios. Confirm the original historical hash is unchanged after the
run. Repeat execution must reproduce numeric tables; compare Windows and
Docker numbers within an explicitly recorded floating-point tolerance.
Inspect figures for complete pair coverage, readable labels, and correct
units. Image-file byte equality is not a completion condition.

The reproduction commands are:

```powershell
uv run --locked python scripts/run_eda.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/02_eda.ipynb
```

The test command runs the whole suite, not only `test_eda.py`. Adding NumPy,
matplotlib, and statsmodels rewrites `uv.lock`, which the Phase 1 build also
uses, so the Phase 1 tests have to pass again. Use the existing workstation
uv/cache and Jupyter-directory setup documented in the README.

The image excludes `data/processed` and `outputs`, so a container cannot read
the workstation's master or results. For the Docker check, run
`scripts/run_pipeline.py --historical-only` in a named container. It rebuilds
the historical master from the raw snapshots and then runs the EDA. The EDA's
hash check then shows that the container's master matches the workstation
file, and no unseen master exists anywhere in that container. The manifest
lookup uses the historical output path, which is present after both full and
historical-only builds. Copy `outputs/metrics/eda/` out with `docker cp` into
a folder outside the project's `outputs/`, compare it with the workstation
tables within the recorded tolerance, and record the result as Phase 1 did.
Document the exact commands after they have been exercised.

## Documentation at completion

Keep adopted definitions and their reasons in `methodology.md`, the work
order here, and observed results in `phase_2_analysis.md`. Define the columns
of the EDA tables in a new section of `data_dictionary.md`, with units and the
allowed statuses. Update `directory_guide.md` when the planned files exist,
and add only verified run commands to the README. Link saved results and execution evidence from the
local phase checklist. Correlation changes and weak relationships are valid
findings; a promising trading pair is not needed to complete EDA.
