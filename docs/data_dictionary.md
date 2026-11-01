# Data dictionary

The master files come first; the Phase 2 EDA tables are at the end.

Both masters have the same 49 columns, including Date. Each row is one stock
trading date. The historical file contains 2,011 rows from 2018-01-02 to
2025-12-31; the unseen file contains 145 rows from 2026-01-02 to 2026-07-31.
CSV has no stored dtype metadata; the types below describe the values, and
consumers should parse Date as a date.

Prices must be finite and positive. Stock volume must be a positive integer.
Open, High, Low, and Close must be internally consistent, although that check
cannot detect every bad print. The source analysis records known limitations.

Returns are `100 * (Close_t / Close_previous - 1)`: 1.5 means 1.5%, not 150%.
The first historical return is empty because no preceding close was downloaded.
The first unseen return uses the last historical close on 2025-12-31.
No other missing values are allowed. The seven empty first-day returns are
preserved as empty CSV fields. Dividends are excluded from returns.

| Column | Meaning | Unit or range | Type | Allowed missing values |
| --- | --- | --- | --- | --- |
| `Date` | Trading date from the Yahoo S&P 500 calendar | YYYY-MM-DD | date | None |
| `MSFT_Open` | Yahoo opening price, split-adjusted as supplied | USD/share | float | None |
| `MSFT_High` | Yahoo daily high, split-adjusted as supplied | USD/share | float | None |
| `MSFT_Low` | Yahoo daily low, split-adjusted as supplied | USD/share | float | None |
| `MSFT_Close` | Yahoo closing price used for returns and later analysis | USD/share | float | None |
| `MSFT_AdjClose` | Yahoo dividend-adjusted close; reference only, excluded from analysis inputs | USD/share | float | None |
| `MSFT_Volume` | Yahoo daily share volume as supplied | shares | integer | None |
| `MSFT_Return` | Daily percentage change in Close; excludes dividends | percent | float | 2018-01-02 in historical only |
| `GOOGL_Open` | Yahoo opening price, split-adjusted as supplied | USD/share | float | None |
| `GOOGL_High` | Yahoo daily high, split-adjusted as supplied | USD/share | float | None |
| `GOOGL_Low` | Yahoo daily low, split-adjusted as supplied | USD/share | float | None |
| `GOOGL_Close` | Yahoo closing price used for returns and later analysis | USD/share | float | None |
| `GOOGL_AdjClose` | Yahoo dividend-adjusted close; reference only, excluded from analysis inputs | USD/share | float | None |
| `GOOGL_Volume` | Yahoo daily share volume as supplied | shares | integer | None |
| `GOOGL_Return` | Daily percentage change in Close; excludes dividends | percent | float | 2018-01-02 in historical only |
| `NVDA_Open` | Yahoo opening price, split-adjusted as supplied | USD/share | float | None |
| `NVDA_High` | Yahoo daily high, split-adjusted as supplied | USD/share | float | None |
| `NVDA_Low` | Yahoo daily low, split-adjusted as supplied | USD/share | float | None |
| `NVDA_Close` | Yahoo closing price used for returns and later analysis | USD/share | float | None |
| `NVDA_AdjClose` | Yahoo dividend-adjusted close; reference only, excluded from analysis inputs | USD/share | float | None |
| `NVDA_Volume` | Yahoo daily share volume as supplied | shares | integer | None |
| `NVDA_Return` | Daily percentage change in Close; excludes dividends | percent | float | 2018-01-02 in historical only |
| `AAPL_Open` | Yahoo opening price, split-adjusted as supplied | USD/share | float | None |
| `AAPL_High` | Yahoo daily high, split-adjusted as supplied | USD/share | float | None |
| `AAPL_Low` | Yahoo daily low, split-adjusted as supplied | USD/share | float | None |
| `AAPL_Close` | Yahoo closing price used for returns and later analysis | USD/share | float | None |
| `AAPL_AdjClose` | Yahoo dividend-adjusted close; reference only, excluded from analysis inputs | USD/share | float | None |
| `AAPL_Volume` | Yahoo daily share volume as supplied | shares | integer | None |
| `AAPL_Return` | Daily percentage change in Close; excludes dividends | percent | float | 2018-01-02 in historical only |
| `AMZN_Open` | Yahoo opening price, split-adjusted as supplied | USD/share | float | None |
| `AMZN_High` | Yahoo daily high, split-adjusted as supplied | USD/share | float | None |
| `AMZN_Low` | Yahoo daily low, split-adjusted as supplied | USD/share | float | None |
| `AMZN_Close` | Yahoo closing price used for returns and later analysis | USD/share | float | None |
| `AMZN_AdjClose` | Yahoo dividend-adjusted close; reference only, excluded from analysis inputs | USD/share | float | None |
| `AMZN_Volume` | Yahoo daily share volume as supplied | shares | integer | None |
| `AMZN_Return` | Daily percentage change in Close; excludes dividends | percent | float | 2018-01-02 in historical only |
| `META_Open` | Yahoo opening price, split-adjusted as supplied | USD/share | float | None |
| `META_High` | Yahoo daily high, split-adjusted as supplied | USD/share | float | None |
| `META_Low` | Yahoo daily low, split-adjusted as supplied | USD/share | float | None |
| `META_Close` | Yahoo closing price used for returns and later analysis | USD/share | float | None |
| `META_AdjClose` | Yahoo dividend-adjusted close; reference only, excluded from analysis inputs | USD/share | float | None |
| `META_Volume` | Yahoo daily share volume as supplied | shares | integer | None |
| `META_Return` | Daily percentage change in Close; excludes dividends | percent | float | 2018-01-02 in historical only |
| `GSPC_Close` | Yahoo S&P 500 price-index close | index points | float | None |
| `GSPC_Return` | Daily percentage change in the S&P 500 Close | percent | float | 2018-01-02 in historical only |
| `VIX_Close` | Cboe official VIX CLOSE on the stock trading date | index points | float | None |
| `Year` | Calendar year of Date | 2018-2026 | integer | None |
| `Quarter` | Calendar quarter of Date | 1-4 | integer | None |
| `Month` | Calendar month of Date | 1-12 | integer | None |

The stock symbols are MSFT, GOOGL, NVDA, AAPL, AMZN, and META. Yahoo prices
are taken from the pinned snapshot; the build makes no further split or
dividend adjustment. AdjClose can reflect dividends after the historical
period, so later analyses must select their intended inputs explicitly.
Calendar fields are integers here; an analysis may encode them differently.

## Aligned checkpoints

`data/interim/aligned_historical.csv` and `aligned_unseen.csv` have the same
trading dates as their corresponding masters. For each stock and GSPC they
retain Open, High, Low, Close, AdjClose, Volume, Dividends, and StockSplits,
prefixed with the symbol. The four Cboe VIX price fields are retained with a
VIX prefix. These checkpoints contain 61 columns including Date, before
returns and calendar fields are calculated. GSPC volume is retained only as a
source field and is not subject to the positive-stock-volume rule.

`Dividends` is the provider's cash distribution per share, and `StockSplits`
is the reported split ratio; zero means no recorded action on that date.
They are finite, nonnegative source values. Corporate actions are preserved
for inspection rather than reapplied to already adjusted Yahoo prices.

`data/interim/excluded_rows.csv` contains Date, Period, Instrument, and Reason.
It lists the 32 Cboe publications inside the formal periods that fall outside
the S&P 500 calendar. It does not list the rest of Cboe's history outside
those periods, which was never part of either master.

## Audit files

`outputs/metrics/phase1_quality_summary.csv` records Period, Instrument, Check,
Status, Count, and Details for each successful check. A failed check raises an
error before output files are replaced. Counts describe the particular check;
for example, allowed missing returns are seven in historical and zero in unseen.

`outputs/metrics/phase1_return_checks.csv` records the sample date, preceding
date and closes, expected return from Decimal arithmetic, actual return, and
absolute error. The acceptable difference is 0.0000000001 percentage points.

`outputs/metrics/phase1_large_moves.csv` records Date, Period, Symbol, Return,
Note, and Source for each absolute daily return above 15%. Historical notes
cite event context. Unseen notes only identify that a flag was recorded.

`data/processed/master_manifest.json` records the periods built, settings,
versions, input and build-file hashes, dataset dimensions, missing-value counts,
and hashes of all eight generated CSVs. The manifest does not hash itself.
It records no wall-clock build time so identical rebuilds can reproduce its
bytes. Acquisition timestamps remain in the source manifests.

## Phase 2 EDA tables

The ten tables in `outputs/metrics/eda/` describe 2018-2025 only. Dates are
`YYYY-MM-DD` strings. Columns ending in `_pct` are percentages in the same
units as the master returns (1.5 means 1.5%). Correlations, beta, and
R-squared are dimensionless. Values keep full calculation precision.

The detailed estimate tables carry `status` (or `<prefix>status`) and the count
and date range of the observations used. Missing estimates have a status
explaining the reason. The matrix is a compact view of the pair table and has
no separate status columns. Drawdown dates are empty when there is no loss,
even when the summary's status is `ok`.

| Status | Meaning |
| --- | --- |
| `ok` | Estimate calculated. |
| `insufficient_observations` | Fewer than `min_observations` (3) observations. |
| `zero_variance` | One input is constant. Correlation is undefined; the adopted policy also omits benchmark fits with a constant stock or benchmark. |
| `incomplete_window` | Rolling window has fewer than 60 paired returns. |

On the real master, every status except the 885 early rolling windows is `ok`.

| File | Rows | Key columns | Other columns |
| --- | --- | --- | --- |
| `stock_summary.csv` | 7 | `instrument` (six stocks and GSPC) | `n`, `first_date`, `last_date`, `base_date` (Close the compounding and drawdown start from), `mean_pct`, `median_pct`, `min_pct`, `max_pct`, `std_pct` (sample, ddof=1), `annualized_vol_pct` (std times sqrt(252)), `compounded_return_pct`, `max_drawdown_pct` (zero or negative), `drawdown_peak_date`, `drawdown_trough_date`, `status` |
| `stock_annual_summary.csv` | 56 | `instrument`, `year` | As above; `base_date` is the previous session (2018-01-02 for 2018) |
| `pair_correlations.csv` | 15 | `pair`, `stock_a`, `stock_b` | `return_correlation`, `return_n`, `return_first_date`, `return_last_date`, `return_status`, and the same five fields with prefix `log_price_` for natural-log Close levels |
| `return_correlation_matrix.csv` | 6 | `symbol` | One column per stock; symmetric, including matching missing values; diagonal is 1 for a varying series with enough observations and empty otherwise |
| `benchmark_sensitivity.csv` | 54 | `stock`, `period` (`2018-2025` or a year) | `alpha_pct` (percent per day), `beta`, `r_squared`, `correlation`, `n`, `first_date`, `last_date`, `status` |
| `pair_annual_correlations.csv` | 120 | `pair`, `stock_a`, `stock_b`, `year` | `correlation`, `n`, `first_date`, `last_date`, `status` |
| `rolling_correlations.csv` | 30,150 | `date` (window end, included), `pair` | `n` (paired returns in the window, up to 60), `correlation`, `status` |
| `vix_group_stock_summary.csv` | 21 | `vix_group`, `instrument` | `n`, `first_date`, `last_date`, `std_pct`, `mean_abs_pct`, `status`; daily units, not annualized |
| `vix_group_pair_correlations.csv` | 45 | `vix_group`, `pair`, `stock_a`, `stock_b` | `correlation`, `n`, `first_date`, `last_date`, `status` |
| `vix_group_year_counts.csv` | 24 | `vix_group`, `year` | `n`, including zero counts |

Pairs are in the fixed display order, with `stock_a` the earlier symbol, so
`MSFT_GOOGL` comes first and `AMZN_META` last. VIX groups are `low`, `medium`,
and `high`; their boundaries are stored unrounded in `run_metadata.json`.
Group dates are pooled and non-consecutive, so no compounded return is given.

## Phase 3 pair-selection tables and spreads

The eight tables in `outputs/metrics/pair_selection/` use the historical
master only. Dates are `YYYY-MM-DD`, counts and ranks are integers, flags are
booleans, and statistical values are floating-point numbers retained at
calculation precision. P-values lie in [0, 1]. Betas, log-price residuals,
R-squared, BIC scores, and test statistics are dimensionless. No column is a
percentage return or trading profit.

`pair_id` keeps the canonical Phase 2 symbol order. `dependent` and
`independent` identify the actual regression direction. `spread_column` puts
the dependent stock first, for example `AMZN_on_NVDA`; it is not the same as
the canonical `NVDA_AMZN` pair identifier. `direction_order` is 0 when the
canonical first stock is dependent and 1 for the reverse. `pair_order` is the
zero-based canonical position. These determine exact tie breaks.

| Fields | Meaning and type |
| --- | --- |
| `fit_start`, `fit_end`, `nobs` | Actual first/last input dates and input observation count for an estimate. |
| `effective_start`, `effective_nobs` | First usable response date and count after differencing or lag loss; the final date is `fit_end`. |
| `intercept`, `beta`, `r_squared` | Log-price OLS coefficients and descriptive fit measure; the spread subtracts both intercept and beta times the independent log price. |
| `regression`, `eg_trend`, `residual_regression`, `autolag` | Deterministic-term and lag-selection conventions: `ct`, `c`, or `n`, and `AIC` as applicable. |
| `maxlag`, `usedlag` | Maximum residual ADF lag considered and the selected lag; nonnegative integers. |
| `statistic`, `pvalue`, `critical_1`, `critical_5`, `critical_10` | Stock-level ADF statistic, ordinary ADF p-value, and 1%, 5%, 10% critical values. |
| `eg_statistic`, `eg_pvalue`, `eg_critical_1`, `eg_critical_5`, `eg_critical_10` | Engle-Granger statistic, inferential p-value, and its appropriate critical values. The p-value decides nominal rejection. |
| `residual_adf_statistic` | No-constant ADF statistic on OLS residuals; checked against `eg_statistic`. Its ordinary ADF p-value is not exported. |
| `levels_lag`, `k_ar_diff`, `det_order` | VAR levels order p, Johansen lagged differences p-1, and Johansen deterministic convention (0). |
| `bic`, `eligible`, `selected`, `lag_at_upper_bound` | VAR BIC score, whether the order is eligible (1-10), whether it was chosen, and whether the choice reaches ten. The curve's estimation dates/counts use a common sample. |
| `trace_stat_r<r>`, `max_eig_stat_r<r>` | Johansen statistics at rank hypothesis r=0 or r=1. |
| `trace_critical_r<r>_<c>`, `max_eig_critical_r<r>_<c>` | Critical values for the same hypothesis at confidence c=90, 95, or 99. |
| `trace_rank_<c>`, `max_eig_rank_<c>` | Sequentially inferred rank 0, 1, or 2, stopping at the first non-rejection. Equality with the critical value does not reject. Rank 2 is full rank, not rank-one support. |
| `reject_unit_root`, `eg_reject`, `johansen_reject`, `holm_reject` | Stock ADF rejection, selected-direction nominal EG rejection, trace rank exactly 1 at 95%, and adjusted pair rejection, respectively. |
| `i1_status`, `i1_consistent` | Stock diagnostic `consistent_with_i1` or `assumption_warning`; pair flag is true only when both stocks have the former status. |
| `eg_pair_pvalue`, `holm_pair_pvalue` | Twice the smaller directional EG p-value capped at 1, then its Holm-adjusted value across 15 pairs. |
| `method_count`, `method_agreement` | Number of nominal methods supporting the pair (2, 1, 0) and corresponding `both`, `one`, or `neither` group. |
| `rank`, `shortlisted`, `evidence_label`, `reason` | One-based final order, membership in the first two, `supported` or `exploratory` under the adopted conditions, and a text explanation. All rows in this run are exploratory. |
| `phi`, `ar_intercept`, `half_life_sessions` | AR(1) slope, intercept, and `-log(2)/log(phi)` in trading sessions when 0 < phi < 1. |
| `period`, `beta_change_abs`, `beta_sign_changed`, `nonpositive_beta` | Stability period `2018_2021` or `2022_2025`, absolute difference between its two betas, a sign-change flag, and a full-period beta <= 0 flag. |

`integration_tests.csv` has 12 rows keyed by `symbol` and `transform`
(`log_level` or `first_difference`). `directional_tests.csv` has 30 rows keyed
by `pair_id`, `dependent`, and `independent`. `lag_selection.csv` has 165 rows
keyed by pair and levels lag. `johansen_tests.csv`, `pair_ranking.csv`, and
`half_life.csv` each have 15 rows keyed by pair. `shortlist.csv` contains the
first two complete ranking rows. `hedge_stability.csv` has 30 rows keyed by
pair and period.

The ranking retains selected directional and Johansen fields. Duplicate
`fit_start_johansen`, `fit_end_johansen`, `nobs_johansen`,
`effective_nobs_johansen`, `effective_start_johansen`, and `status_johansen`
refer to the system test rather than the directional fit. `status` is `ok`
for successful fits; failures stop the run rather than leave partial rows.
`half_life_status` (or `status` in `half_life.csv`) can be `ok`,
`nonpositive_phi`, `non_mean_reverting`, `constant_spread`, or
`insufficient_observations`. An undefined half-life is empty, with its status
explaining why. Undefined coefficients for constant or insufficient samples
are also empty. All real-run half-life statuses are `ok`; that is not a
cointegration label.

`data/processed/pair_spreads_historical.csv` contains Date and 15 oriented
spread columns over 2,011 sessions, with no missing values. Each is
`log(dependent_Close) - intercept - beta * log(independent_Close)`. They are
unnormalized in-sample residuals, not Z-scores. The matching JSON under
`artifacts/statistical/phase3_v1/<PAIR_ID>/` records the coefficients, symbol
orientation, transformation, model version, fit dates/count, evidence label,
shortlist flag, input/settings hashes, and library versions. No normalization
or model for the 2024-2025 LSTM validation is fitted here.

`run_metadata.json` inventories output hashes, config/code/lock hashes,
versions, run checks, warning records, and the actual fitting windows of the
leakage audit. Casting warnings with exactly real Johansen eigenvalues are
recorded; nonzero imaginary components or non-finite statistics are errors.
