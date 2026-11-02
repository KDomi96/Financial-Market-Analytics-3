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

## Phase 4 statistical baseline

The tables use `pair_id`, `dependent`, `independent`, `spread_column`,
`evidence_label`, `period`, `model_version`, and `evaluation_label` as common
identifiers. `period` is historical or unseen; `evaluation_label` is
`in_sample` or `unseen_fixed_parameters`. Both pairs remain `exploratory`.
`trade_id` is unique within a pair and period, so join using all three keys.
Dates are ISO daily trading dates. Cash, prices, exposures, and P&L are USD.
Returns, proportions, win rates, and drawdowns are fractions, not percentages.

`data/processed/statistical_baseline/{historical,unseen}_zscores.csv` has one
row per pair/session: `Date`, unnormalized log-price `spread`, fixed `zscore`,
and the common identifiers. Neither numeric field permits missing values.
Normalization artifacts in `artifacts/statistical/phase4_v1/<PAIR_ID>/` store
`mean`, `std`, `ddof=1`, actual `fit_start`, `fit_end`, `nobs`, orientation,
OLS path/hash, historical/config hashes, version, and library versions.
Normalization statistics are in log-residual units.

Backtest tables live under
`outputs/backtests/statistical_baseline/phase4_v1/{historical,unseen}/`:

| Table | Columns and meaning |
| --- | --- |
| `signals.csv` | `Date`, `previous_z`, `zscore`, and `position` after that day's Open fill. `outside_long/short`, `long/short_crossing`, `eligible_long/short`, and `exit_signal` are booleans. `action` is `hold`, `enter_long`, `enter_short`, or `exit`. |
| Signal order fields | `ignored_reason` is empty, `position_open`, or `exit_priority`. `order_status` is `none`, `filled`, `unfilled_end_of_period`, or `stopped_nonpositive_equity`. `execution_date` and `trade_id` link a filled order to its stock-leg fills. |
| `executions.csv` | One row per stock leg/fill: `Date`, `signal_date`, `trade_id`, `action`, `leg` (dependent/independent), signed `shares_change`, observed Open `price`, absolute `turnover`, and charged `cost`. A buy increases shares; a sell reduces them. |
| `trades.csv` | One row per paired entry. `direction` is +1 long spread or -1 short spread. Signal dates (`entry_signal_date`, `exit_signal_date`) are separate from fill dates (`entry_date`, `exit_date`); an open trade has empty exit dates. `status` is `closed` or `open`; `mark_date` is the exit date or final observed Close date. |
| Trade holdings and prices | `q_dependent/independent` are fixed signed share quantities. `entry_dependent/independent` and `mark_dependent/independent` are prices. `entry_gross_notional` is the sum of absolute entry stock values. `entry_net_exposure` and `mark_net_exposure` are signed sums. |
| Trade results | `dependent_pnl/independent_pnl` are gross stock-leg contributions. `gross_pnl` is their sum, `costs` contains only incurred charges, and `net_pnl` deducts them. `gross_return/net_return` divide by entry gross notional. `holding_sessions` is mark-session index minus entry-session index; an open trade's duration is incomplete. |
| `daily_account.csv` | Close-time `q_dependent/independent`, `position` (-1/0/+1), active `trade_id`, and `fill_trade_id` for an entry/exit that morning. `cash` includes short proceeds and incurred charges. `dependent_exposure/independent_exposure` are signed Close stock values; `net_exposure` sums them and `gross_exposure` sums their absolute values. |
| Daily results | `dependent_pnl/independent_pnl` include overnight and intraday moves on the quantities actually held. `net_pnl/gross_pnl` are changes in account equity, with initial capital before the first session. `cumulative_costs` reconciles `gross_equity - net_equity`. `net_drawdown/gross_drawdown` include initial capital in the running peak. |

`previous_z` is missing on the first historical session. An unfilled or absent
order has an empty execution date. Open trades have empty exit dates and exit
signal dates. Flat days have no active trade ID. An exit day's `fill_trade_id`
can remain populated when `trade_id` is empty. There are no missing numeric
prices, holdings, or P&L values. Empty trade or execution tables retain headers.

Metric tables live under
`outputs/metrics/statistical_baseline/phase4_v1/{historical,unseen}/`:

| Table | Columns and meaning |
| --- | --- |
| `summary.csv` counts | `long/short_outside_days`, `long/short_crossings`, `long/short_signals` (eligible entries), `long/short_executed_entries`, and `long/short_closed_trades`. Totals include `executed_entries`, `closed_trades`, `open_trades`, `exit_signals`, `ignored_crossings`, and `unfilled_orders`. |
| Summary performance | `initial_capital`, `final_net_equity`, `final_gross_equity`, `net_return`, `gross_return`, `total_costs`, `closed_net_pnl`, `open_net_pnl`, each leg's P&L, `max_drawdown_net/gross`, `peak_gross_exposure`, and `peak_abs_net_exposure`. Account return uses initial capital. |
| Trade averages | `win_rate` uses closed trades with strictly positive net P&L. `mean_closed_trade_return` and `mean_closed_holding_sessions` use closed trades only. These three fields are missing when none close, with `trade_metric_status=no_closed_trades`; otherwise it is `defined`. |
| Run status | `status` is `complete` or `incomplete_nonpositive_equity`; `sessions` counts simulated account rows. An incomplete account stops at its last recorded mark and must not be reported as a completed evaluation. |
| `spread_diagnostics.csv` | `sessions`, `min_z`, `max_z`, `mean_z`, `long/short_outside_days`, `long/short_outside_proportion`, and `long/short_longest_outside_run`. Long means below -2; short means above +2. Run lengths are trading sessions. |
| `reversion_events.csv` | One row per eligible entry signal: `signal_date`, `direction` (long/short), first later qualifying `zero_date`, `observation_end`, and `sessions_observed` from signal close to zero close or the endpoint. `status` is `reverted` or `right_censored`; the latter has no zero date. |
| `unseen/market_exposure.csv` | One row per unseen trade, written by notebook 04 after the run. Keys: `pair_id`, `trade_id`, `direction`, `status`, `dependent`, `independent`, `evidence_label`, `period`, and `model_version`, as in `trades.csv`. Values: `window_start`/`window_end` (entry and exit signal closes, or the final close for an open trade), `sp500_return` (decimal), `market_beta_exposure` (USD, signed shares times entry Open times each stock's 2018-2025 S&P 500 beta from Phase 2), `market_part` (USD, exposure times S&P 500 return), and `gross_pnl` (USD). A single-factor estimate, not an exact attribution. |

`run_metadata.json` holds actual windows, input/config/code hashes, settings,
normalization, versions, validation, warnings, leakage audit, and output/figure
hashes. The parent `evaluation_contract.json` protects the fitted objects and
historical inputs/settings/code used by an evaluated version. The unseen
master hash is retained and checked in its period's run metadata. No-trade
runs have zero counts, costs, return, and drawdown, with missing trade averages.

## Phase 5 LSTM forecasts and comparison

Phase 5 rows identify `pair_id`, `dependent`, `independent`, `evidence_label`,
and `stage`. Both pairs are exploratory. `selection` uses the earlier OLS and
2023 scale; `final` uses the Phase 3 OLS and Phase 4 scale. `validation` and
`unseen` identify evaluation periods. Join forecast rows by pair, trial,
origin, and horizon, not target date alone. Forecasts from different origins
can refer to the same target date.

| Saved table or artifact | Fields and meaning |
| --- | --- |
| Processed `features.csv` | `Date`, `z`, `lag1/lag2/lag3`, and `rolling_std`: trailing 20-session sample standard deviation including Date. The first 19 rolling values are missing; lag warm-up values are missing. No warm-up row enters an input tensor. Values are in the stage's Z units. |
| `sample_index.csv` | `split`, `input_start`, `input_end`, `origin`, `origin_z`, and `target_h1` through `target_h5`. Inputs contain 20 rows and targets are the five following sessions. The model target is `Z(target_h) - origin_z`. |
| `excluded_samples.csv` | `origin` and `reason`: insufficient feature history, targets before the period, target crossing the end boundary, or incomplete future targets. Exclusions contain no fabricated targets. |
| Earlier OLS and `normalization_2023.json` | Direction, intercept/beta, fit dates/counts; normalization `mean`, sample `std`, `ddof=1`, and `resting_z=-mean/std`. The same resting-level calculation applies to the final normalization. |
| `scaler.json` | Ordered features, column `mean` and `scale`, `ddof=0`, distinct `fit_dates`, fit bounds/count, constant-column flags, pair/stage identity, and parent OLS/normalization. A constant column uses scale 1. |
| `forecasts.csv` | `origin`, horizon 1-5, `target_date`, observed `origin_z`, `predicted_change`, reconstructed `forecast_z`, realized `actual_z`, `persistence_z=origin_z`, and `trial_id`. All values are finite Z units. |
| `trials.csv`, `epoch_history.csv` | Architecture/rate/seed, candidate or sensitivity role, selected epoch and run length; training/validation MSE by epoch. Final epoch history has missing validation MSE because final fitting has no validation/stopping set. |
| Forecast metrics | `model` is LSTM or persistence; `horizon` is 1-5 or pooled. MAE/RMSE are in Z units. `origins`, `predictions`, and `unique_target_dates` expose denominators. `rmse_improvement` is `1 - model RMSE / persistence RMSE`, missing when persistence RMSE is zero. |
| Direction diagnostics | Day-five predicted change, observed change derived from `actual_z-origin_z`, `direction_correct`, raw `crossing`, `would_accept_crossing`, and stage `resting_z`. Sign equality defines correctness, including a zero-change tie. These fields do not select a model. |
| `seed_agreement.csv` | Accuracy and agreement with seed 42, overall or at forecast-covered crossing origins. Fractions use the stated origin count; empty subsets have missing proportions. Base-rate columns (`phase5_v2` onward) give the accuracy of rules with no model on the same origins: `majority_sign_rate` (the more common realized sign), `toward_resting_rate` (sign of `resting_z - origin_z`), and `toward_zero_rate` (sign of `-origin_z`). `predicted_rise_share` is the share of origins with a positive predicted change. |
| `filter_decisions.csv`, `unseen_filter_decisions.csv` | One row per state-eligible entry in the filtered account (`phase5_v2` onward): signal `Date`, `direction`, `zscore`, day-five forecast and predicted change, `resting_z`, calendar/acceptance flags, order status, and the realized `actual_z_h5` on `target_date_h5`. `direction_correct` compares the predicted and realized day-five signs and is missing when the origin has no scored forecast. Realized values were joined after the backtest finished. |
| Final bundle | `model.pt` state dictionary; metadata with architecture, epoch rule, fit/target bounds, feature order, embedded OLS/normalization/scaler, historical session calendar, runtime, weights hash, and preprocessing digest. `known_inference.json` holds dated historical prices and five expected Z forecasts. |

Comparison ledgers retain the Phase 4 units and accounting fields. The
additional signal booleans are `entry_calendar_eligible`, `entry_accepted`,
`calendar_excluded`, and `filter_rejected`. `eligible_long/short` still mean
position-state eligibility before calendar/filter checks. `forecast_z_h5` and
`predicted_change_h5` are missing for the unfiltered baseline and dates without
a scored forecast. Exits still depend on observed Z.

In `phase5_v2`, `ignored_reason` keeps its Phase 4 values (empty,
`position_open`, or `exit_priority`), so `ignored_crossings` counts the same
events as the Phase 4 summary. Calendar exclusions and forecast rejections
appear only in their own flags and counts. In the retained `phase5_v1` files,
`ignored_reason` can also be `calendar_excluded` or `forecast_rejected`, and
`ignored_crossings` includes those entries.

`strategy` is `baseline_matched`, `lstm_filtered`, or the saved reference
`baseline_full_period`. Summary fields add `filter_rejections`,
`calendar_exclusions`, `accepted_entries`, `submitted_orders`, and
`entry_eligible_origins`. The full-period reference has missing values for
these new fields. Win rate and other closed-trade averages are undefined
when no trade closes. Account P&L still includes the marked open position.

`selection_metadata.json`, `refit_metadata.json`, and `unseen_metadata.json`
inventory hashes and checks. `split_audit.csv` lists actual fitted-object
dates. `evaluation_contract.json` fixes code/settings/input/artifact hashes;
`evaluation_started.json` also protects the evaluated unseen input hash,
including a run interrupted before its final metadata is saved.

## Sentiment study

The sentiment settings are in `configs/sentiment.json`. Source responses and
text-bearing tables stay local. Committed summaries contain counts, model
scores, labels, and record IDs. They do not contain news or benchmark text.

### Local inputs and scored records

| File or field | Meaning |
| --- | --- |
| Raw benchmark manifest | Dataset revision, licence note, canonical URL, download time, file size, SHA-256, and structural counts. PhraseBank is used only for the overlap screen. |
| Raw news manifest | Pilot/full role, acquisition settings and fingerprint, intended root/leaf windows, every request attempt and response hash. A window is pending, split, success, capped, or failed. A capped window still returned at least 100 raw items after splitting to one day. |
| `record_id` | Original benchmark row identifier prefixed by its dataset; disagreements can be located in the local source snapshot. |
| `gold_label`, `gold_score` | FiQA's fixed derived class and original numeric score in `[-1, 1]`; FinEntity's native lower-case class and a missing numeric score. |
| `text`, `target` | Benchmark text and its annotated entity; present only in the ignored interim tables. |
| `headline_id` | First 24 hex characters of SHA-256 of the queried ticker and RSS GUID. |
| `raw_title`, `text` | Original RSS title and the cleaned headline after removing a matching publisher suffix. Both remain local. |
| `publisher`, `publisher_source_url`, `google_news_url` | RSS source name, its source URL, and the Google News article link. The source URL is not assumed to be a direct article URL. |
| `reported_time_raw`, `reported_time_utc`, `reported_date` | Original `pubDate`, timezone-aware UTC time, and its UTC calendar date, used for local request-boundary checks. |
| `date_only`, `analysis_date` | Pacific-midnight items use their Pacific date. Other items use the next applicable saved trading session under the close rule. Neither establishes historical availability. Items outside the analysis window are excluded. |
| `collected_at_utc`, `window_id`, `guid` | Collection time and request window of the response that supplied the kept copy, and the RSS record identifier. Narrower requests are read before the split windows they replaced. Collection time is not substituted for publication time. |
| `capped_window`, `split_window` | The kept copy came from a one-day request still at 100 items, or from a 100-item response whose window was then split. |
| `publisher_suffix_unmatched` | True when the title did not end with the exact source-name suffix; the title was left unchanged. |
| `p_positive`, `p_negative`, `p_neutral` | FinBERT probabilities in `[0, 1]`, summing to one within floating-point precision. The model's output order is read from its saved configuration. |
| `predicted_label`, `score` | Highest-probability class and `p_positive - p_negative` in `[-1, 1]`. These are model estimates, not gold labels for the news. |
| `token_count`, `truncated` | Tokenized length including special tokens, and whether it exceeded the fixed 512-token limit. |
| `vader_compound`, `vader_label` | Benchmark-only compound score and class under the fixed inclusive +/-0.05 boundaries. |
| Exclusion log `reason` | The first applicable rule, including invalid items, out-of-window dates, unrelated company, several companies, duplicate GUID/title, multiple annotations, invalid entity span, benchmark duplicates, or PhraseBank overlap. Duplicate GUIDs are mostly copies returned by both a split window and one of its parts. Counts follow the recorded cleaning order. |

### Daily and weekly summaries

These tables are in `data/processed/sentiment/sentiment_v2/`. The
`sentiment_v1` folders hold the first run, kept for comparison.

| Field | Meaning and missing values |
| --- | --- |
| `ticker`, `date` | One of the six stocks and each calendar date from 1 January to 31 July 2026. The daily table includes weekends and holidays. |
| `observed_headline_count` | Number of retained scored records assigned to the date, even when collection is incomplete. |
| `headline_count` | Observed count when coverage is complete; missing when a source query failed or a source-timing gap affects the date. Capped counts are lower bounds and remain flagged. A successful uncapped empty day has zero. |
| `mean_score` | Headline-weighted mean of model scores; missing with no retained headlines or incomplete coverage. It is never filled with zero for an empty day. |
| `date_only_share` | Fraction of retained daily records with Pacific-midnight timestamps; missing with no retained records. |
| `direct_request_complete` | All intended leaf requests covering that reported date succeeded or were capped. |
| `source_timing_gap` | A failed or capped source date could have contributed timed items to this next trading session. The original uncertainty is propagated once. |
| `request_complete`, `capped` | Direct coverage plus the source-timing adjustment. Capped data remain marked even when a request succeeded. |
| `week_end` | Friday ending a Saturday-Friday calendar week. Weekly scores weight headlines rather than daily means. |
| `partial_study_week` | Fewer than seven study dates, including the initial 1-2 January window. Such weeks are excluded from comparisons. |
| `sparse_pilot_coverage` | The company failed the pilot's four-usable-weeks rule. Its counts remain visible but trend comparisons are omitted. |
| `comparison_eligible` | A full week with complete, uncapped coverage, at least one retained headline, and a company that passed the pilot. |

### Metrics and comparisons

Files are under `outputs/metrics/sentiment/sentiment_v2/`. Confusion matrices
use gold labels as rows and predicted labels as columns, in negative,
neutral, positive order. Accuracy, precision, recall, F1, and confidence limits
are fractions. Bootstrap intervals use 1,000 paired row resamples and seed 42.
FiQA MAE/RMSE compare a classifier score with its numeric targets; they do not
make FinBERT a calibrated regression model.

`weekly_market_comparison.csv` adds the compounded saved percentage returns
as `weekly_return` in fractional units and records the trading-session count.
`weekly_return_associations.csv` gives Spearman correlation and the number of
eligible weeks; an undefined correlation is missing. Pair differences are the
dependent stock's weekly mean score minus the independent stock's.

`entry_signal_context.csv` has two stock rows for each eligible Phase 4 entry.
`lookback_sessions` lists the five sessions ending before the signal date.
Counts and mean scores refer only to those sessions; signal-day counts are
separate. Date-only items are not assigned to sessions, so weekend and
holiday headlines between the five sessions are not counted. Completeness and cap flags accompany both the lookback and signal
day. Missing means can reflect no headlines or incomplete coverage, as shown
by the counts and flags. No statistical inference is made from five events.

Run metadata records the model revision, settings, source/model/market input
hashes, code hashes, lock hash, counts, collection status, and, by company,
how many kept copies came from split-window responses. Reproduction
records identify the compared outputs and numerical tolerance. Headline
scoring does not fit or modify the Phase 1-5 artifacts.
