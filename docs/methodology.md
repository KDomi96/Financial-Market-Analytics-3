# Methodology and decisions

This document records the analytical and engineering choices made for the
project and the reasons for them. Completion criteria and evidence are tracked
separately in the local phase checklist; data provenance is in
[data sources](data_sources.md).

Each decision carries one of three statuses:

- **Adopted:** agreed and to be implemented as written. Changing it requires a
  recorded reason and an updated entry here.
- **Proposed:** the planned default. It may be refined during implementation,
  but must be fixed before the results it affects are evaluated.
- **Open:** not yet decided.

Decisions that affect the unseen period (2026-01-01 to 2026-07-31) must be
fixed before that period is evaluated. They are never revised in response to
unseen results.

## Decision log

| Area | Decision | Status |
| --- | --- | --- |
| Phase 6 sentiment | No sentiment page or route; the sentiment study stays a separate experiment and is not used as a signal | Adopted |
| Sentiment rules | One finance-term query per company; titles must name the company; titles naming several of the six left out; VADER thresholds of ±0.05; pilot pass rule; weekly comparisons; headline text and model files kept out of Git | Adopted |
| Sentiment collection | Plan direct English/US Google News RSS collection in short date windows, with saved responses and coverage checks; use date summaries when publication times cannot support session assignment | Adopted |
| Sentiment evaluation | Reuse FiQA headline scores and FinEntity entity labels for two separate benchmarks of the unchanged FinBERT checkpoint; replace the earlier SEntFiN-only plan and manual annotation task; keep benchmark results separate from the six-stock news study | Adopted |
| Phase 6 serving | API and app containers read the saved Phase 5 models, processed masters, and Phase 3 tables from read-only mounts; forecast origins end at 2026-07-31; no sentiment page until the sentiment results exist | Adopted |
| Phase 6 application | Uploaded CSV or the project's prices; one pair tested with Phase 3 settings and called cointegrated when the direction-adjusted Engle-Granger p is at most 0.05 and the Johansen trace rank is one; normalization from the final year before a chosen fit end; Phase 4 signals; exploratory view for failing pairs; saved Phase 5 models on a separate forecast route | Adopted |
| Phase 5 trading filter | Accept a fresh long/short entry only when the day-five forecast moves in the reversion direction; retain Phase 4's observed-Z exits | Adopted |
| Phase 5 targets and batch order | Train on five-session changes in Z and add them to the origin's Z for the forecast; shuffle training windows each epoch with a seeded generator | Adopted |
| Phase 5 implementation defaults | 20-session trailing volatility, training-only feature scaling, four compact LSTM candidates, persistence comparison, and matched entry calendars | Adopted |
| Phase 4 design | 2025 mean and `ddof=1` std; enter on ±2 crossings while flat, exit when Z reaches 0, exit takes priority, start flat; separate USD 10,000 accounts; beta-weighted fixed shares sized at the next open; 5 bps per leg; mark open trades at the final close | Adopted |
| Phase 3 design | ADF lags by AIC and Johansen VAR order by BIC; direction by the smaller Engle-Granger p-value; Holm over 15 pair-level p-values; rank by method agreement, then Engle-Granger p-value; stop on any failed fit; shortlist of two | Adopted |
| Phase 2 scope | Compare return and risk, cover all 15 pairs and benchmark sensitivity, examine relationships by year and with rolling correlations, and add VIX context | Adopted |
| Phase 2 methods | Pearson return and log-price correlations, return/risk definitions, OLS beta with intercept, 60-session rolling window, VIX terciles | Adopted |
| Docker runtime | One image; ordered batch pipeline as the default command; API and app as two containers from that image | Adopted |
| LSTM device | CPU-only PyTorch build; final models and reported metrics produced on CPU | Adopted |
| Build reproducibility | Verify only selected Yahoo periods; slice shared Cboe history before price checks; omit wall-clock time from the build manifest | Adopted |
| Data sources | VIX close from Cboe; stocks and S&P 500 from Yahoo; IBKR used only to check Yahoo | Adopted |
| Master layout | Column set, hard stops instead of filling, 15% move flag, `\n` line endings | Adopted |
| Prices | Close drives returns, spreads, and P&L; dividends are omitted and documented | Adopted |
| Calendar fields | Master stores integer Year, Quarter, and Month; each analysis encodes them as needed | Adopted |
| Pair selection | If no pair qualifies, carry forward the strongest candidates labelled exploratory | Adopted |
| LSTM splits | Select on 2018-2023 training / 2024-2025 validation, then refit through 2025 | Adopted |
| Execution | Signal after the close on day t; fill at the open on day t+1 | Adopted |
| LSTM framework | PyTorch | Adopted |
| Sentiment | Google News headlines scored locally with FinBERT; standalone descriptive study | Adopted |
| API and app | FastAPI API; Streamlit interface calling it over HTTP; local Docker first | Adopted |

## Phase 1: Master data

### Data sources (Adopted)

The six stocks (OHLC and volume) and the S&P 500 come from the Yahoo snapshot.
VIX comes from Cboe's official daily history. IBKR daily bars were downloaded
as an independent reference for checking Yahoo; nothing from IBKR goes into
the master. IBKR's subscriber agreement does not allow redistributing its
data, so nothing from IBKR is committed.

Yahoo and IBKR agree on every trading date and on every stock close to within
0.1%. Against Cboe, Yahoo's VIX close is wrong on three days, including
2026-02-06 in the unseen period (20.37 against 17.76), so the whole VIX series
is taken from Cboe. Yahoo's S&P 500 close differs from IBKR's on one day
(2021-08-11, 0.12%); Yahoo's value is kept and the difference recorded as a
limitation, because patching single values from another provider is harder to
reproduce and explain than the error is worth. The full comparison is in the
[Phase 1 source analysis](phase_planning/phase_1_analysis.md).

Open prices differ between Yahoo and IBKR on many days, but on 97-99% of
historical days per stock by less than 0.15%. Yahoo's open is used, including
as the execution price in the backtests; that it may not be the official
opening auction price is recorded as a limitation.

### Price series (Adopted)

Returns, cointegration spreads, and trading P&L all use Yahoo Finance `Close`.
`Adj Close` is retained in the master for reference only.

Yahoo's `Close` is already split-adjusted. The snapshot contains every split in
the period (AAPL 4:1 on 2020-08-31, NVDA 4:1 on 2021-07-20 and 10:1 on
2024-06-10, AMZN 20:1 on 2022-06-06, GOOGL 20:1 on 2022-07-18), and `Close`
shows no artificial jumps at those dates.

`Adj Close` additionally adjusts for dividends, but it was computed at download
time, after the unseen period ended. Its historical values therefore include dividends paid in
2026: on 2025-12-31 the Adj Close/Close ratio is 0.9973 for AAPL and 0.9937 for
MSFT, not 1.0. Using it would place information from the unseen period in the
training data, and its values would depend on the download date.

Consequence: returns and P&L exclude dividends. Over the period the cumulative
dividend adjustment reaches about 8.6% for MSFT and 6.6% for AAPL (Adj
Close/Close of 0.914 and 0.934 on 2018-01-02), less for the others, and zero for
AMZN. This is reported as a limitation. The short leg's dividend obligation is
omitted for the same reason, so the treatment is consistent across both legs.
Split adjustment in `Close` is also applied retrospectively, but the unseen
snapshot contains no splits.

### Trading calendar (Adopted)

The S&P 500 trading dates in the Yahoo snapshot define the calendar: 2,011
historical and 145 unseen dates, identical to the six stocks' dates. The Cboe
VIX series must have a close on every one of those dates. Cboe also publishes
VIX on some days when stocks did not trade (27 historical and 5 unseen,
including 2026-05-25); those rows are excluded and listed in the exclusion
log. No stock observations are created for closed-market dates. IBKR has the
same trading dates as Yahoo, which supports the calendar, but a date missing
from every source would still not be detected.

Daily returns larger than 15% in either direction are flagged and their cause
noted. A flag never changes the data; genuine market moves are kept even when
large.

### Returns (Adopted)

Daily percentage returns are `(Close_t - Close_{t-1}) / Close_{t-1} * 100` for
each stock and the S&P 500. The first historical return (2018-01-02) has no
preceding close in the snapshot and is left missing; no warmup data are
downloaded. The first unseen return (2026-01-02) uses the 2025-12-31 close,
which was known at that time.

### Calendar fields (Adopted)

The master stores `Year`, `Quarter`, and `Month` as integers. A helper converts
them to another encoding only when an analysis needs one:

- Linear models and regressions use one-hot dummies with one category dropped
  per group, because an integer implies a linear ordering and all dummies plus an
  intercept are perfectly collinear.
- Tree models can use the integers directly.
- Neural networks would need one-hot, embedding, or cyclical encoding.

Calendar fields are not LSTM inputs unless a later recorded decision adds them.

### Dataset layout (Adopted)

The historical and unseen masters are built by the same function and saved
separately as CSV, with a common schema and one row per trading date. The wide
layout places pair members side by side. Columns:

- For each stock: `_Open`, `_High`, `_Low`, `_Close`, `_AdjClose`, `_Volume`,
  and `_Return`, prefixed with the symbol (for example `MSFT_Close`).
  `AdjClose` is a labelled reference column, not an analysis input.
- `GSPC_Close` and `GSPC_Return`. Index volume is left out because Yahoo's is
  unreliable (zero on 2023-05-24).
- `VIX_Close`, from Cboe's CLOSE. The VIX open, high, and low are not needed.
- `Year`, `Quarter`, and `Month`.

Dividends and split records stay in the interim checkpoints rather than the
master. A missing or duplicated date, or an invalid required price, stops the
build; values are never filled, interpolated, or silently dropped. CSVs are
written with `\n` line endings so the same data give the same file hash on
Windows and in Docker. A data dictionary, an exclusion log, and a manifest of
input and output hashes accompany the files. File names and the order of work
are in the [Phase 1 plan](phase_planning/phase_1_plan.md).

The historical-only command checks only the selected historical Yahoo files.
The Cboe snapshot is one shared history file, so its hash covers the whole
file, but its prices are restricted to the requested period before validation
or alignment. The unseen return receives the last aligned historical row in
memory, the same row saved in the historical checkpoint. These implementation
details preserve the historical build's independence from Yahoo's unseen files.
The build manifest omits a wall-clock run time so repeating an unchanged build
also reproduces the manifest bytes; acquisition times remain in the raw manifests.

## Phase 2: Exploratory analysis

### Scope (Adopted)

The analysis compares the six stocks' returns and risk, examines all 15 stock
pairs, and describes each stock's sensitivity to the S&P 500. Annual
comparisons and rolling correlations show how those relationships change
within the historical period. A small VIX investigation adds context about
market uncertainty. Month/quarter pattern investigations remain optional,
outside this agreed scope.

The only market-data input is `data/processed/master_historical.csv`.
These are retrospective descriptions of 2018-2025, not out-of-sample tests.
All 15 pairs continue to Phase 3; an EDA correlation does not qualify or
exclude a pair. Cointegration tests, spread regressions, and pair ranking
belong to that phase.

### Return and risk measures (Adopted)

Use the existing Close-based percentage returns, with dividends excluded.
Include the S&P 500 as a reference alongside the six stocks in the performance
and risk summaries. Report the same measures for the whole period and each
calendar year:

| Measure | Definition and unit |
| --- | --- |
| Daily return summary | Arithmetic mean, median, minimum, maximum, and sample standard deviation; all in percent |
| Compounded price return | `100 * (product(1 + daily_return / 100) - 1)`; percent, kept separate from the arithmetic mean |
| Annualized volatility | Sample standard deviation of daily percentage returns times `sqrt(252)`; percent, annualized |
| Maximum drawdown | Minimum of `100 * (wealth / running_peak - 1)`; zero or negative percent |

Use `ddof=1` explicitly for sample standard deviation. The divisor is `N - 1`,
as described in the [pandas standard-deviation documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.std.html).
The 252-day factor is a fixed reporting convention, not an estimate of the
number of sessions in each year or a forecast of future volatility.

For the whole-period performance chart, index each Close to 100 on the first
historical date. Its endpoint must agree with compounding the valid returns.
The first historical return remains missing and is excluded from return
statistics. It does not become a zero-return observation. For annual
calculations, group the existing returns by their dates; retain each later
year's first-session return from the preceding year's final Close. The 2018
return covers the first observed Close onward because no 2017 Close is present.

Drawdown uses a wealth path starting at 1, including that starting value when
calculating the running peak. Reset this starting wealth for each annual
summary, so a loss on the first session of a later year is counted. Annual
drawdowns describe losses within that year; the whole-period drawdown can
span several years. They are labelled separately.

### Pair relationships (Adopted)

Use Pearson correlation of same-day daily returns as the main comparison.
Save all 15 unique unordered pairs, their sample counts, and a six-stock
correlation matrix. Each pair gets a time-series panel of
`log(Close_t / Close_first)` and a scatterplot of the two daily returns.
The former is in natural-log units; the latter uses percentage returns.

Also report Pearson correlation of the log-price levels in the pair table,
labelled separately from return correlation. This comparison illustrates how
similar trends can produce high level correlations without establishing a
stable equilibrium. Neither measure is evidence of cointegration.

### Benchmark sensitivity (Adopted)

For each stock, fit `stock_return = alpha + beta * GSPC_return + error`, using
same-day percentage returns and an explicit intercept. Save beta, alpha in
percent per day, R-squared, stock/benchmark return correlation, sample count,
and the actual observation dates. Repeat the regression within each calendar
year to show changes in sensitivity.

The [statsmodels OLS documentation](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLS.html)
states that an intercept must be supplied when using the array interface.
After explicitly removing the permitted first historical missing-return row,
use an error on any remaining missing observation rather than silent deletion.
Beta describes the fitted association with the benchmark: a one percentage
point benchmark move corresponds to a fitted beta percentage point stock move.
It is not a causal effect, a cointegration hedge ratio, or a CAPM estimate
using excess returns. Alpha is not presented as evidence of investment skill.
P-values and confidence intervals are outside this descriptive analysis.

### Relationship stability (Adopted)

Compare daily-return correlations for all 15 pairs within each calendar year.
Alongside them, use one fixed trailing window of 60 trading observations,
approximately three months, for every pair. Require 60 valid paired returns,
include the current day's return, and label each result by the window's end
date. These are after-close descriptive plots, not trading inputs. Windows
continue across calendar years and never use future observations.

Do not try several window lengths and retain the one producing the most
attractive relationship. The 60-day window was fixed before any EDA result
was calculated. Early incomplete windows stay missing.
Constant-return windows also have undefined correlation and stay missing with
a recorded reason. pandas does not mark them itself: in pandas 3.0.6,
[`Rolling.corr`](https://pandas.pydata.org/docs/reference/api/pandas.api.typing.Rolling.corr.html)
returned `inf` for a constant window in a synthetic check, while the rolling
standard deviation returned exactly zero. Zero variance is therefore detected
from the inputs before an estimate is accepted. Constant or insufficient
samples in static correlations or benchmark regressions likewise produce
missing estimates with a status, not invented zeros or infinities.

### VIX context (Adopted)

Plot the historical VIX and compare stock volatility and pair correlations
across low-, medium-, and high-VIX groups. VIX measures expected S&P 500
volatility over the next 30 days, as explained by
[Cboe](https://www.cboe.com/tradable_products/cboe_minis/vix_mini_vix/).
This provides context for changing stock relationships: greater market
uncertainty may coincide with different volatility and correlations. The
analysis checks whether those differences exist rather than assuming them.

Use the Cboe `VIX_Close` already aligned in the historical master. The
groups use the historical VIX's one-third and two-thirds quantiles, estimated
on dates with valid returns for all six stocks and the benchmark. Use linear
quantile interpolation. Low is at or below the lower boundary, medium is
above the lower boundary and at or below the upper boundary, and high is
above the upper boundary. Tied VIX values stay together, so group sizes need
not be equal. The labels describe relative VIX levels within this historical
sample. Record both boundaries and the dates used to estimate them.
This rule is set before viewing the grouped results; the numerical boundaries
are calculated during the EDA run.

Within each group, report daily-return sample standard deviation and mean
absolute daily return for the six stocks and S&P 500, and Pearson daily-return
correlation for all 15 stock pairs. Use same-date VIX and returns. Volatility
and mean absolute return are in daily percentage units; correlation is
dimensionless. Save observation counts and dates.
Also show group counts by year, so a result dominated by one historical
episode is visible. Each group pools non-consecutive dates; it is not a
continuous holding period, and no compounded group return is calculated.

These comparisons describe historical associations. They do not establish
cointegration or add VIX to the LSTM or trading rules. If a later decision
uses VIX for prediction, its thresholds must be fitted within that stage's
training window and its information must be available at the prediction time.
No 2026 observations enter this investigation.

### Adoption

The methods above were reviewed and adopted before any of them
was calculated on the historical master: Pearson return correlations, the
log-price comparison, the return/risk definitions, OLS benchmark sensitivity
with an intercept, the fixed 60-session rolling window, and the VIX grouping
rule. The work order, planned outputs, and verification are in the
[Phase 2 plan](phase_planning/phase_2_plan.md).

## Phase 3: Pair selection

### Pair handling when evidence is weak (Adopted)

If no pair shows adequate cointegration evidence, the strongest candidates are
carried into later phases and labelled exploratory throughout. They are not
described as established cointegrated pairs. Given the divergence of these
stocks over 2018-2025, weak results are a realistic outcome.

### Test design (Adopted)

These settings were fixed before any Phase 3 result was calculated. The
[Phase 3 plan](phase_planning/phase_3_plan.md) gives the work order and files.

Use natural logs of the six stocks' Close prices over 2018-2025. All 15 pairs
continue regardless of EDA correlation. The fixed stock and pair order is the
same as Phase 2. The significance threshold is 5%; p-values at or below 0.05
reject, while a statistic exactly equal to a Johansen critical value does not.

**Integration checks.** Run `adfuller` on each log-price series with
`regression="ct"` (constant and linear trend) and on its first difference with
`regression="c"`. Use `autolag="AIC"` and an explicit maximum lag of
`ceil(12 * (n / 100) ** 0.25)`, capped at `n // 2 - d - 1`, where n is the
input length and d is the number of deterministic regressors: 2 for `ct`,
1 for `c`, and 0 for a residual test with `regression="n"`. This is the
library's default rule, written out so a change of default cannot change the
results. AIC chooses the lags because too few lags leave autocorrelation in
the test regression and make the test reject too often, and AIC tends to keep
more lags than BIC.

Failure to reject a unit root in levels, together with rejection in first
differences, is labelled consistent with I(1). It does not prove I(1).
Rejection in levels or failure to reject in differences gives an assumption
warning. Keep every pair in the comparison, but label its interpretation
exploratory if either stock has that warning. ADF has limited power and these
checks are a diagnostic, not another search for whichever specification passes.

**Directional fits and Engle-Granger.** Fit
`log(A) = intercept + beta * log(B) + residual` in both directions for all
15 pairs. Use `coint(log_A, log_B, trend="c", method="aeg", autolag="AIC",
maxlag=...)`, with the lag rule above and d=0 for its residual ADF step.
The spread has an intercept but no time trend: later phases study deviations
around a fixed fitted relationship, rather than around a moving trend.

Save both directions and choose the one with the smaller raw Engle-Granger
p-value. An exact tie selects the direction with the earlier stock in the
fixed display order as dependent.

The inferential p-value and 1%, 5%, and 10% critical values come from `coint`.
A matching `adfuller(residual, regression="n", ...)` supplies the selected lag
and effective sample count, which `coint` does not expose. Its statistic must
match the Engle-Granger statistic within the recorded tolerance. An ordinary
residual ADF p-value is not exported as cointegration evidence: it does not
account for estimating the relationship first.

Rejection is decided by the p-value. `coint` takes its p-value from
MacKinnon's asymptotic table but its critical values from the finite-sample
table, so with 2,011 observations the two can disagree only for a statistic
between -3.339 and -3.336.

Any failed regression, non-finite statistic, or collinearity warning stops
the run with an error. This includes the negative-infinite statistic and zero
p-value that `coint` returns for near-collinear inputs. With six large-cap
stocks over 2,011 sessions this guards against a broken input, not a
statistical outcome, so failed fits are not carried through the ranking.

**Johansen.** Run `coint_johansen` for every pair with `det_order=0`, the
library's constant-term convention, without searching other deterministic
settings. This is a separate system test; its deterministic specification is
not claimed to be identical to the single-equation Engle-Granger model.

Choose lag order using the BIC curve returned by
`VAR(log_prices).select_order(maxlags=10, trend="c")`. Compare levels orders
1-10 on the equal-length samples used by that routine; select the minimum BIC,
breaking an exact tie in favour of the smaller order. Keep order zero in the
saved curve but exclude it from selection, because the planned Johansen model
needs a levels order of at least one. Pass `k_ar_diff = p - 1`, where p is
the selected levels order. Record a warning if p reaches the upper bound;
do not expand the search after seeing the cointegration result. BIC is used
here, rather than the AIC used for ADF, because unnecessary short-run lags cost
the Johansen test power, and BIC settles on the true order as the sample grows
while AIC tends to overshoot.

Save trace and maximum-eigenvalue statistics for rank hypotheses 0 and 1,
their 90%, 95%, and 99% critical values, and a sequential rank for each method
at each level. Start at rank zero and stop at the first non-rejection. At 95%,
trace rank 1 means rejecting rank zero but not rank at most one. Rank 2 in a
two-series system is full rank, which conflicts with the intended two-I(1)
interpretation; it is not confirmation of one cointegrating relationship.
Trace rank 1 supplies the main Johansen comparison flag. Maximum-eigenvalue
disagreement remains visible. The implementation supplies no p-values, so
none are inferred from the critical-value tables.

### Comparison and shortlist (Adopted)

The two directions of a pair test the same hypothesis, that the two stocks are
not cointegrated, so the multiple-testing family has 15 members rather than
30. Each pair gets one p-value: twice the smaller of its two directional
Engle-Granger p-values, capped at 1. The doubling accounts for choosing the
better direction. `multipletests(..., alpha=0.05, method="holm")` is applied
to these 15 values. Its first step needs a directional p-value at or below
0.05/30, the same bar as an adjustment over all 30 directions, but each
adjusted result now refers to a pair rather than to one direction of it. The
30 raw directional p-values stay in the saved results. The adjustment checks
conclusions that rest on the smallest of many tests; it does not correct
model misspecification. Johansen's results are not adjusted and are not an
independent replication, because both methods use the same historical prices.

Pairs are ranked first by whether the two methods agree at the 5% level:
both, one of them, or neither. Engle-Granger counts when the selected
direction has p at or below 0.05; Johansen counts when the trace test gives
rank exactly 1 at 95%. Two tests rejecting together is stronger evidence than
a slightly smaller p-value from one test. Within each group, pairs are ordered
by the selected direction's raw Engle-Granger p-value, and the fixed pair
order breaks an exact tie. The raw, doubled, and Holm-adjusted p-values give
the same order within a group, so the adjustment affects the label below but
not the ranking.

A shortlisted pair is labelled supported only when both stocks' diagnostics
are consistent with I(1), its Holm-adjusted pair p-value is at or below 0.05,
and its Johansen trace rank at 95% is exactly 1. Otherwise it is exploratory.
Supported means evidence under these specifications, not proof of a permanent
relationship or a profitable trade. The individual flags are kept even when
they disagree with the overall label.

The shortlist is the first two pairs in the ranking. Fixing the number before
any result exists keeps the later baseline and LSTM comparison manageable and
avoids choosing the count after seeing the results. If one or both lack the
evidence above, they are carried forward with exploratory labels and an
explanation, following the adopted weak-evidence policy. The specification is
not changed to produce qualifying results.

### Supporting diagnostics (Adopted)

Fit `spread_t = a + phi * spread_(t-1) + error_t` to each selected-direction
historical spread. For 0 < phi < 1, report the discrete AR(1) half-life
`-log(2) / log(phi)` in trading sessions. Other coefficients have no
conventional half-life. Unlike a failed fit, a spread that does not revert is
a possible result, so it is saved with a status instead of stopping the run.
This is an in-sample approximation, not a second stationarity test or a
forecast of a future holding period.

Refit each selected direction separately over 2018-2021 and 2022-2025, with
the same intercept convention. Save both intercepts, betas, counts, and actual
dates. Show the absolute beta change and sign change without a new pass/fail
threshold. The two fits describe historical variation; they do not replace
the full-period relationship or alter its rank. Neither diagnostic selects
a window, a direction, or a trading rule.

Save each selected spread with its orientation and full-period coefficients
so later phases can reconstruct
`log(price A) - intercept - beta * log(price B)`. Spread columns are named
`<dependent>_on_<independent>`, for example `AAPL_on_NVDA`, because the pair
identifier alone does not say which stock is dependent. Phase 3 does not fit its
2025 normalization. The planned Phase 4 parameters and the adopted Phase 5
refitting windows remain as recorded below.

## Phase 4: Statistical baseline

### Spread and normalization (Adopted)

The saved Phase 3 regression fitted on 2018-2025 defines the spread. Load its
full-precision intercept, beta, and stock orientation rather than fitting it
again. Carry AMZN_META (AMZN on META) and NVDA_AMZN (AMZN on NVDA) forward with
their exploratory labels. Their residual means and standard deviations are
estimated over 2025 only. The unseen Z-score is

`Z(t) = (spread(t) - mean_2025) / std_2025`

using the sample standard deviation (`ddof=1`). Pass this argument explicitly:
[NumPy defaults to `ddof=0`](https://numpy.org/doc/stable/reference/generated/numpy.std.html).
Fewer than two observations, a zero or non-finite standard deviation, or a
non-finite residual stops the run. Neither the regression nor the normalization
parameters are refitted on 2026. Save the actual normalization dates, count,
mean, standard deviation, and source artifact hashes.

### Trading rules (Adopted)

- Long entry crossing: `Z(t-1) >= -2` and `Z(t) < -2`.
- Short entry crossing: `Z(t-1) <= 2` and `Z(t) > 2`.
- An existing long exits when `Z(t) >= 0`; an existing short exits when
  `Z(t) <= 0`. Equality triggers an exit but does not trigger an entry.
- Enter only while flat, with at most one open position per pair. Crossings
  during a position are recorded but ignored. There is no pyramiding.
- An exit takes priority over an opposite crossing. Close the position at the
  next open; a new entry needs a fresh crossing on a later signal date. There
  is no reversal order or delayed entry from an ignored crossing.
- Start the unseen run flat, with no pending order. The last 2025 Z-score is
  comparison context for the first 2026 close only. No December signal is
  executed in January. If the spread is already outside the band and remains
  there, it produces no entry until a fresh crossing occurs.
- Fix the thresholds before evaluation. No stop-loss, maximum holding period,
  or threshold search is included in this first baseline. These omissions
  allow prolonged losses and must remain visible in the findings.

Crossings distinguish new excursions from repeated days outside the band.
Daily conditions would permit an entry immediately after starting outside the
band; that is a different strategy. Save counts of both outside-band days and
raw crossings so this choice does not hide the observed spread behaviour.

### Execution and accounting (Adopted)

- **Timing (Adopted):** signals are computed after the close on day t and
  executed at the open on day t+1. Exits follow the same rule. The equity curve
  is marked at each close. Overnight gaps between close and next open are part
  of the result. Here t+1 means the next available trading session, not the
  next calendar day. A queued market order fills even if the next open gaps
  beyond the signal level; it is not cancelled using later information.

The accounting details are:

- **Accounts:** evaluate each pair in a separate USD 10,000 account. Both
  spreads contain AMZN, so do not add their returns or describe the results as
  an independently diversified portfolio. Capital is a reporting convention,
  not an estimate of broker margin requirements.
- **Sizing:** let C be initial capital, E the net account equity while flat,
  and c the transaction-cost rate. At entry, set gross notional
  `G = min(C, E) / (1 + c)` and `N = G / (1 + abs(beta))`. This reserves the
  entry cost, reduces sizing after losses, and does not increase the budget
  after gains. Position sizes are determined from the net account for both
  gross and net reporting.
- **Holdings:** with direction s equal to +1 for long spread and -1 for short,
  use `q_dependent = s * N / open_dependent` and
  `q_independent = -s * beta * N / open_independent`. Allow fractional shares
  and hold these quantities until exit. The current shortlist has positive
  betas; reject a nonpositive beta for review instead of silently creating a
  different exposure. The log-price slope is an elasticity, not a share ratio.
  The hedge is therefore not dollar-neutral. With USD 10,000, a long AMZN on
  META spread holds about USD 6,250 of AMZN against USD 3,750 of META, and a
  long AMZN on NVDA spread about USD 8,060 of AMZN against USD 1,930 of NVDA.
  Because beta is below one, a move shared by both stocks also changes the
  spread and the P&L: a 10% rise in both adds about USD 250 or USD 610 to a
  long position. Save net exposure and each leg's P&L for every trade and day
  so the findings can show this.
- **Costs:** charge `0.0005 * sum(abs(shares_traded) * execution_price)` on
  every entry and exit. This is an assumed combined allowance for commission
  and slippage, not a measured broker quote. Record fills at the observed Open
  and costs separately; do not also adjust prices for slippage. Assume complete
  fills and short availability. Omit short-borrow fees, financing, cash interest,
  dividends, and broker margin rules, and state these limitations.
- **Cash:** start with C. For signed share changes dq, update cash by
  `-sum(dq * execution_price) - cost`. At each close,
  `equity = cash + sum(held_shares * Close)`. Short proceeds enter cash but do
  not increase the sizing budget. Daily net P&L is the change in equity, with
  C as the initial reference. The first entry day includes Open-to-Close P&L;
  an exit day includes the previous Close-to-exit-Open move.
- **Gross comparison:** use identical fills and quantities, adding cumulative
  charged costs back to net equity. This isolates the cost drag; it is not a
  separately resized zero-cost strategy.
- **Boundaries:** mark any position still open on 2026-07-31 at that Close.
  Include its unrealized P&L and entry cost in equity, flag it as open, and
  exclude it from closed-trade averages and win rate. Do not assume a final
  liquidation or deduct an exit fee that was not incurred. A last-day signal
  remains in the signal table with `unfilled_end_of_period`; never read August
  prices to fill it. Nonpositive equity stops the simulation with an explicit
  incomplete status, rather than continuing as a solvent account.

Cash P&L comes from both stock legs, not from changes in the log spread. The
fixed holdings approximate the fitted log relationship at entry; their dollar
weights drift afterwards. Record both legs' exposure through the trade.

### Counts, returns, and diagnostics (Adopted)

Report long and short counts separately for outside-band days, raw crossings,
eligible entry signals while flat, executed entries, and closed trades. The
headline signal counts are the eligible entry signals; the other counts show
how much that choice affects the picture. A trade is one paired entry
followed by its exit, not two stock orders. Save ignored crossings with their
reasons, exit signals, and final unfilled orders. Check
`executed entries = closed trades + positions still open` per pair/run.

For each closed trade, net return is net trade P&L divided by its own entry
gross notional G. Report the mean closed-trade return, closed-trade cash P&L,
open-trade P&L, and total account return `(final_equity - C) / C` separately.
Do not sum trade percentages and call that account return. Win rate is the
number of closed trades with strictly positive net P&L divided by the number
of closed trades; break-even trades are not wins. With no closed trades, win
rate and average closed-trade return are missing with an explanatory status.

Maximum drawdown is the largest `1 - equity / running_peak_equity`, including
C before the first session. Report gross and net versions. Holding time is
the difference between entry and exit session indices; use the final session
as the endpoint for an open position and flag it as incomplete. A no-trade run
has zero account return and drawdown, zero counts, and missing trade averages.

Describe unseen spread behaviour using the Z-score plot, counts and proportion
of sessions above +2 and below -2, longest consecutive outside-band runs, and
whether each eligible entry excursion later reaches its zero exit level.
Measure the latter from the signal close to the first later qualifying close,
in trading sessions. Excursions that have not returned by the endpoint are
right-censored, not dropped or given an invented reversion time. These are
descriptions of the evaluation period, not fresh pair-selection tests or
proof of a stable equilibrium.

The Phase 3 half-lives are 77.5 and 104.1 sessions against 145 unseen
sessions, so each pair may produce only one or two unseen trades, or none.
Trade-level metrics are then descriptive, and a single trade can decide the
win rate. That is reported as found and is not a reason to change the
thresholds.

### Historical checks and evaluation order (Adopted)

First exercise the engine on small known examples. Then run it over
2018-2025 with the saved full-history coefficients and fixed 2025 normalization,
starting flat with no crossing available on the first historical row. Label
the entire run in-sample: even early historical observations use later fitted
information. It checks implementation and describes fitted-period behaviour;
it is not independent validation or a basis for claiming achievable returns.

Freeze these rules in config before the first unseen run. Record the config,
code, input, and fitted-artifact hashes. Corrections after evaluation need a
logged reason and preserved earlier results; do not quietly replace a losing
run. Phase 5 must share the accounting and comparable evaluation dates, while
its forecast and trading choices are selected using historical data only.
The observed Phase 4 results must not become a tuning target for Phase 5.

The 2025-only normalization centers Z on the recent residual mean. If the
2025 spread was unusually quiet, a modest 2026 drift can keep |Z| above 2 for
months and produce one long losing trade. That would be reported as found.

## Phase 5: LSTM forecasts and strategy comparison

### Fitting stages (Adopted)

| Stage | Spread regression | Z normalization | LSTM training | Evaluated on |
| --- | --- | --- | --- | --- |
| Model selection | 2018-2023 | 2023 residuals | 2018-2023 targets | 2024-2025 validation |
| Final refit | 2018-2025 | 2025 residuals (Phase 4 parameters) | 2018-2025 targets | January-July 2026 |

The selection stage fits the whole process, including regression and
normalization, on the training portion only. Validation therefore does not
reuse a spread already fitted on the validation years. The pair shortlist was
still chosen on 2018-2025, so validation is conditional on that shortlist and
is not independent validation of pair selection. This limitation is disclosed.
Validation backtests size trades with the 2018-2023 selection beta, not the
full-history beta, which was fitted partly on the validation years.

The final refit has no validation set. It trains for the epoch count selected
in the selection stage. Its unseen Z-scores are identical to Phase 4's, so both
strategies trade the same series and no scale conversion is needed.

### Inputs and targets (Adopted)

- Features per day, in order: Z, Z lag 1, lag 2, lag 3, and trailing rolling
  standard deviation of Z. The rolling window is 20 trading sessions,
  with `ddof=1` and all 20 observations required. It includes the current close,
  which is known at the after-close prediction origin. The explicit lag
  columns overlap with information already in the sequence.
- An origin after the close on day t uses the 20 trading days ending at t and
  predicts Z for t+1 through t+5.
- Training samples whose target window crosses into a later split are dropped.
  Earlier observations may supply input context to later splits.
- Unseen origins run from 2025-12-31 to the last origin with a complete
  five-day target. The origin count is reported.
- Any feature scaler is fitted on the training portion only and saved.

The feature scaler subtracts each column's mean and divides by its
population standard deviation (`ddof=0`). Fit it on the union of dates used
in training input windows, once per date. Flattening overlapping windows
would count middle observations repeatedly. A constant column gets scale 1
and a recorded flag; missing or non-finite values fail. Targets are the
five-session changes described below, in stage-specific Z units and not scaled
further; adding the origin's Z gives the forecast. There is no clipping or refitting on validation or unseen
values. These five means/scales can be saved as JSON and applied with NumPy;
an additional preprocessing library is unnecessary.

This input scaling serves the optimizer and is separate from spread
normalization. The selection scaler uses the earlier-fit Z series; the final
scaler is fitted again using the final-fit series. Never mix these objects.
Twenty feature rows with a trailing 20-session statistic need 39 consecutive
spread observations. Keep insufficient-context rows visible in the exclusion
audit rather than padding them.

### Model (Adopted)

PyTorch was chosen for explicit control over the training loop, early
stopping, and the final-refit epoch rule. Models are saved as `.pt` files with
metadata: pair, feature order, window lengths, split dates, seed, training
device, and library versions. Use a separate compact network for each pair:
one unidirectional LSTM layer, followed by a linear head from its last hidden
state to five outputs. Forecast all five horizons together, without feeding
realized future Z values back into the model. Reset hidden/cell state for
each sequence. The [PyTorch LSTM interface](https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html)
supports this recurrent layer; the five-output linear head is a project
choice. The settings are:

| Setting | Value |
| --- | --- |
| Candidate grid | Hidden units 16 or 32, crossed with learning rates 0.001 or 0.0003: four configurations per pair |
| Fixed architecture | Five inputs, one recurrent layer, five linear outputs, no dropout |
| Training | Float32, MSE averaged across samples and horizons, Adam, zero weight decay, batch size 64, seeded shuffling (adopted, see below), gradient norm capped at 1 |
| Selection budget | At most 200 epochs; stop after 20 epochs without validation MSE improving by more than `1e-6` |
| Checkpoint | Save the first epoch and replace it on an improvement greater than `1e-6`; restore that checkpoint for scoring |
| Configuration choice | Lowest pooled validation RMSE; within `1e-6`, prefer fewer hidden units, then the lower learning rate |
| Seeds | Seed 42 for all four selection candidates and final refit; seeds 7 and 2026 for two additional validation checks of the selected design |
| Final epoch count | Best saved epoch from the selected seed-42 trial, with no early stopping during final refit |

The small grid tests capacity and learning rate without turning this dataset
into a large search. Select by forecast error separately for each pair, not
by trading returns. The two extra seeds describe sensitivity; they do not
replace the selected checkpoint, change the epoch rule, or select a lucky
seed. Record all trials and numerical failures. A non-finite loss or gradient
stops the run for investigation. Poor forecasts do not justify silently
adding more trials. Validation errors are selection evidence, not an unbiased
estimate for the selected model.

### Targets and batch order (Adopted)

The network predicts the five changes `Z(t+h) - Z(t)` for h = 1 to 5. The
forecast for each horizon is `Z(t)` plus the predicted change, and errors and
the filter use that forecast level. A model that predicts no change reproduces
persistence, so its errors show what the LSTM adds beyond it. Final-stage
levels range from about -9 to +8 while five-session changes have a standard
deviation near 0.5, and level targets would spend most of the loss on a level
persistence already gets right. Changes also depend less on each stage's
resting level, which makes the selected epoch count safer to reuse in the
final refit. The change is a different target, not extra information: the
inputs and their dates are unchanged.

Training windows are shuffled every epoch by a generator seeded with the
trial's training seed. The date split already keeps validation targets out of
training, so batch order is an optimization choice, not a leakage control.
In date order, every epoch would end on the latest months of the training
period. Validation, evaluation, and inference keep date order.

### Training device (Adopted)

Training and inference run on CPU, using the CPU-only PyTorch build on both
Windows and Docker. Each pair contributes under 2,000 short sequences to a
small network, so CPU training should take minutes at most, and a GPU would
add little speed at this size. The CUDA build would add several gigabytes of
packages, and its GPU kernels do not reproduce CPU results exactly. With a
rule that picked the GPU whenever one was present, the reported metrics would
depend on the machine that trained the model.

The device is saved in each model's metadata. If tuning on the validation
years turns out to be slow, a GPU may be used for those trials only. Final
models and reported metrics are always produced on CPU.

For the implementation, fix Python, NumPy, and PyTorch seeds, use
one intra-op and one inter-op CPU thread, no data-loader workers, and enable
deterministic operations. Save the runtime settings. This reduces run-to-run
variation but does not guarantee identical training between Windows and
Linux; [PyTorch documents that limitation](https://docs.pytorch.org/docs/stable/notes/randomness.html).
Test repeated training and artifact reload separately. Record platform
differences instead of changing seeds until results agree.

### Evaluation (Adopted)

Report MAE and RMSE for horizons 1-5 for each pair. For N complete origins,
pooled MAE is the mean absolute error over all `5*N` origin/horizon cells;
pooled RMSE is the square root of their mean squared error. It is not the
average of the five horizon RMSEs. Report N, prediction count, and distinct
target-date count. Overlapping horizons reuse target dates, so these cells
are not independent observations; do not attach an independence-based
significance claim to a small difference.

Persistence repeats the origin's observed Z at all five horizons and uses
the same target keys as the LSTM. Report the absolute errors and the relative
RMSE improvement, `1 - RMSE_LSTM / RMSE_persistence`; this ratio is undefined
when persistence error is zero. Keep the first implementation to this
benchmark. An AR(1) comparison would be a separately recorded extension.
Forecast quality is assessed separately from trading results.

RMSE does not measure the one quantity the filter uses, the sign of the
predicted day-five change. On validation, I also report how often that sign
matches the realized five-session change, overall and at crossing origins,
and how many crossing decisions the two extra seeds share with seed 42. In
the selection training data, the mean five-session change after Z > 2 was
-0.10 and -0.04 against a standard deviation of 0.60 and 0.48, so these
decisions may be fragile. The diagnostics are reported only; they select
nothing.

### LSTM-enhanced strategy (Adopted)

Use a fixed day-five direction filter on fresh statistical entry crossings
while that strategy is flat. Accept a long only if `forecast_z_h5 > Z_t`,
and a short only if `forecast_z_h5 < Z_t`. Equality rejects the entry. There
is no optimized margin, horizon search, or forecast-based exit. I chose
this fixed rule to keep the comparison simple
and avoid another layer of strategy tuning.

Observed-Z exits, exit priority, next-open execution, sizing, costs, and
endpoint marking remain those of Phase 4. A rejected crossing expires;
remaining outside the band does not create a later entry. Each strategy
has its own holdings and evaluates crossings against its own current state.
Do not filter an already executed baseline ledger.

The signed forecast change tests movement in the reversion direction. It
does not require the predicted endpoint's absolute Z to be smaller: a
forecast can overshoot zero. Keep that distinction in the interpretation.
The filter also cannot predict the next-open gap or guarantee profitable
stock-leg P&L. Do not tighten the rule after examining unseen trades.

Z = 0 is the last year's mean, not the level the spread has returned to over
the regression window. OLS residuals average zero over their fit window, so
that level sits at `-mean / std` in each stage's Z units. A planning check put
it near 2.78 for NVDA_AMZN in the selection stage, above the +2 short
threshold, and near -0.47 in the final stage. A model that learned to revert
toward it would treat a validation short crossing as a move away from
equilibrium. I save each stage's level and report it with the filter
decisions instead of changing the rule.

### Comparison calendar and reporting (Adopted)

Score forecasts from the final historical close through the last origin
whose five target dates are all inside the evaluation period. For trading,
start both accounts flat on the first evaluation session, use the last
historical Z only as crossing context, and carry no order from the previous
year. A preceding-year origin is therefore scored but cannot initiate an
evaluation trade.

Restrict new entries in both strategies to evaluation-period origins with
complete five-day targets. This restriction uses the calendar only. Keep
processing observed-Z exits, next-open fills, and close marks through the
endpoint. Preserve the original full-period Phase 4 baseline alongside this
matched baseline and the LSTM-filtered result, so the calendar restriction's
effect remains visible. Apply the same convention to historical validation.

Report raw crossings, entries eligible under position state, calendar
exclusions, filter acceptances/rejections, submitted orders, executed entries,
closed trades, and final open trades separately. State each denominator.
Compare gross/net account return, net P&L, costs, drawdown, and closed-trade
win rate using Phase 4's definitions. No closed trades means an undefined win
rate, not zero. Keep leg P&L and net/gross exposure available; these pairs
share AMZN and are separate accounts, not a diversified portfolio.

Both strategies' rules and the final model artifacts are frozen before the
Phase 5 evaluation. Phase 4's 2026 results have already been seen, so the
period is held out from model fitting but is not a newly untouched test.
Do not use those results to choose model settings, filters, or exclusions.
Retain any corrected evaluated run and record why it changed.

### Implementation and reproduction (Recorded)

Inference validates input
sessions against the saved training calendar. Later dates require an
independent supplied session calendar, so a missing price row cannot quietly
shorten a lookback. The ordered pipeline validates and retains a handoff
already frozen by Phase 4; a fresh Docker run still rebuilds it. This preserves
the earlier lockfile provenance after torch is added.

Reported Phase 5 artifacts use the Windows CPU runtime. The plan defined two
separate reproduction checks. Inference with identical saved weights must meet
the float32 tolerance, and it does on Linux. Retraining on another platform
must reproduce dates, samples, the selected configuration and epoch, and every
trading decision, and Linux retraining does. The plan did not apply the float32
tolerance to retrained weights, which PyTorch does not promise to reproduce
across platforms. The measured forecast difference after Linux retraining is
recorded as a platform difference, not as a failed check. It does not prompt
a new model, seed, or filter search.

The first evaluated run, `phase5_v1`, was repeated as `phase5_v2` with
identical settings after review. The rerun adds direction base rates and a
dated filter-decision table, draws persistence on the learning curves, keeps
`ignored_reason` in its Phase 4 meaning, and moves a pipeline helper into the
package. None of these changes touches features, training, selection, the
filter rule, or accounting, and the v1 files are kept unchanged. The rerun was
needed because the evaluation contract fixes the code of an evaluated version.

## Sentiment

### Source and role (Adopted)

Headlines are collected from Google News RSS for the six companies, with
headline, publisher, URL, and publication time preserved. Scoring uses a
pretrained financial sentiment model (FinBERT, `ProsusAI/finbert`) run locally.
The X/Twitter API is not used because historical search access is paid.
News sentiment measures financial-media coverage, not discussion on X.

Sentiment is a standalone descriptive study: trends, article counts, and
changes over time across the six stocks, and their relation to returns and
spread signals. It is not an LSTM input. Headlines collected now cannot show
what was available at a past prediction time, which is a further reason not to
use them as model inputs.

### Evaluation (Adopted)

Use two existing labeled datasets instead of manually labeling 150-300
headlines. The earlier SEntFiN-only plan was replaced to
cover both short financial headlines and longer paragraphs with entity
annotations. The model remains `ProsusAI/finbert`, without fine-tuning.

- **FiQA 2018 Task 1 headlines:** preserve the target-specific numeric sentiment
  scores in `[-1, 1]`. The [organizer page](https://sites.google.com/view/fiqa/home)
  describes the task. Its download links were unavailable, so the local snapshot
  uses a pinned [challenge participant's mirror](https://github.com/dayanfcosta/fiqa-2018-task1).
  It contains 438 labeled headline records with 503 target scores. The separate
  93-headline test file contains inputs but no gold scores and cannot supply
  test accuracy. The mirror's counts differ from those reported in the original
  [challenge paper](https://andrefreitas.org/papers/www_fiqa_2018.pdf); the saved
  snapshot counts are the counts used here.
- **FinEntity:** use the [authors' release](https://github.com/yixuantt/FinEntity)
  of 979 paragraphs with 2,131 positive, negative, or neutral entity
  annotations. The [paper](https://arxiv.org/html/2310.12406) describes its human
  annotation and consistency checks. The source contains 390 paragraphs with
  exactly one annotation, before duplicate and span checks. This subset can
  evaluate whole-paragraph sentiment against the one annotated entity; it is
  not an evaluation of entity recognition or the full multi-entity task.

The original file names and split names are retained. Using labeled FiQA
records from a file called `train` does not mean fitting FinBERT on those
records. They are an external evaluation collection for this fixed checkpoint,
subject to the overlap check below. Acquisition details and source issues are
recorded in [data sources](data_sources.md#sentiment-benchmark-snapshots).

Financial PhraseBank is part of FinBERT's documented fine-tuning data, as
stated in its [model card](https://huggingface.co/ProsusAI/finbert).
Screen normalized benchmark text against that dataset and exclude matching
records before scoring. Do not treat an evaluation on the whole
Financial PhraseBank as independent evidence. The overlap screen checks the
documented fine-tuning corpus; it cannot prove the absence of all prior
training exposure.

Report each benchmark separately, with class counts, macro-F1, accuracy,
per-class precision/recall/F1, and a confusion matrix. Compare against VADER
with thresholds fixed before scoring and a majority-class reference derived
from the benchmark's class counts.
Use the existing labels for disagreement examples; no new manual annotation
is required. The benchmark is for evaluation, not model or threshold tuning.

Neither benchmark establishes accuracy on the six companies' 2026 Google News
headlines or validates their collection and company-matching rules. The news study
therefore reports model-estimated sentiment and coverage, without a measured
accuracy claim for that collection. Its input window still depends on the
coverage pilot.

### Benchmark preparation (Adopted)

- Keep records with exactly one annotation for each benchmark. Retain the
  complete source files, but exclude multi-annotation records from the simple
  whole-text evaluation. A text that appears in several records carries all
  of their annotations, so a headline listed again for a second target is
  excluded, while an exact repeat keeps one copy. Record all exclusion counts
  and cross-dataset overlap.
- Remove duplicate evaluation texts and exclude FinEntity records whose saved
  entity value does not match the annotated text span. Do not repair labels
  or spans silently. The download check found 11 duplicate paragraph texts and
  70 span/value mismatches in the full FinEntity source; usable subset counts
  are determined during preparation.
- Take the overlap-screen input from Financial PhraseBank v1.0, the zip in the
  [`takala/financial_phrasebank`](https://huggingface.co/datasets/takala/financial_phrasebank)
  repository, at a pinned revision. Screen against the 50%-agreement file,
  which contains every sentence in the three stricter files. Exclude a
  benchmark record when its normalized text equals a PhraseBank sentence or
  contains one, since a paragraph can include a sentence without being equal
  to it. Containment counts only for sentences of at least five words; the
  shorter entries are greetings and fragments that occur in ordinary text, so
  they count only by an exact match. The file is used only for this screen
  and is never scored.
- Derive FiQA classes using fixed boundaries: below `-0.3` is negative, above
  `0.3` is positive, and the inclusive middle interval is neutral. This is a
  project mapping, not a native FiQA label. Fix it before model evaluation and
  do not search for boundaries that improve the result. Also report MAE, RMSE,
  and the Spearman correlation of `P(positive) - P(negative)` against the
  original scores as separate diagnostics; the classifier score is not a
  calibrated FiQA regression model.
- Classify VADER's compound score with the thresholds its authors recommend:
  at least `0.05` is positive, at most `-0.05` is negative, and anything in
  between is neutral.
- Keep FinEntity's original classes. Present headline and paragraph results
  separately, with their different target definitions and retained counts.
- Add seeded bootstrap 95% intervals for accuracy and macro-F1. Each prepared
  benchmark keeps a few hundred records, so a difference of a few points
  between FinBERT and VADER may be noise.

### Procedure (Adopted)

The ordered steps, file list, and checks are in the
[sentiment plan](phase_planning/sentiment_plan.md). The pilot may still change
the queries, names, or cleaning rules, but only on counts and relevance, never
on scores, and each change is recorded here with its reason.

- Save a collection pilot before the full run: the first full Monday-Friday
  week of each month from January to July 2026, for each company. A sampled
  week is usable when at least five headlines remain after the relevance,
  several-company, and duplicate rules, about one per trading day. The full
  collection goes ahead if at least four companies have at least four usable
  weeks out of seven. A company below that is still collected, but its results
  are reported as sparse coverage without trend comparisons. If fewer than four
  companies pass, revise this procedure before collecting. Pilot headlines are
  not scored, so queries and rules are chosen from counts and relevance only.
  RSS search does not give a complete news archive; the study reports
  retrieved coverage. The preliminary requests are described in
  [data sources](data_sources.md#google-news-rss-preliminary-requests).
- Use the RSS feeds directly, with English/US settings. The preliminary
  requests needed no API key or new dependencies. Each company has one query:
  its names and tickers joined by `OR`, followed by
  `(stock OR shares OR earnings)`. The finance terms keep results to coverage
  of the company as a business and a stock, and none of them favours positive
  or negative stories. The names are Microsoft and MSFT; Alphabet, Google,
  GOOGL, and GOOG; Nvidia and NVDA; Apple and AAPL; Amazon and AMZN; and Meta.
  Google is a subsidiary, but it is how most headlines name Alphabet. Product
  and other subsidiary names are not used, so each company is matched the same
  way.
- Query short date windows and split those returning 100 items into smaller
  windows. Record a possible limit if a one-day window still returns 100.
  Read every saved successful response during cleaning, including those of
  split windows, because the narrower requests can miss items that the wider
  request returned.
  Query each window one day wider on each side and keep items by their
  reported date, because the preliminary requests returned items dated on the
  `before:` day. Save unchanged responses, queries, requested windows,
  collection times, hashes, request outcomes, and retries. Respect rate limits
  and retain failed windows for resumption rather than treating them as days
  without news.
- Google News matches a query against more than the title, so a headline counts
  for a company only when its title names that company, using the names above
  as whole words regardless of case. Titles naming two or more of the six
  companies are left out of the company series and counted. A whole-headline
  prediction cannot say which company its sentiment is about, and both
  benchmarks are scored only on records with one annotated target.
- Before those checks, remove the trailing ` - Publisher` that RSS adds to a
  title when it matches the item's source name. Otherwise copies of one story
  from different publishers would not match, and the model would read
  publisher names. Within a company, titles equal after Unicode normalization,
  lower case, and single spacing are duplicates; keep the earliest reported
  time. Preserve the original title, publisher, Google News link, reported
  publication time, and any verified publisher URL or time. Do not require
  article-body access. The cleaning rules are fixed before any headline is
  scored.
- Keep reported publication time separate from collection time and historical
  availability. Treat an item as date-only when its reported time is exactly
  midnight in `America/Los_Angeles`. Both preliminary historical requests fit
  this: 08:00 UTC in January and 07:00 UTC in July. A single UTC hour would
  misread items after the daylight-saving change on 8 March 2026. Summarize
  date-only items by date, without inventing a time or applying an after-close
  rule.
- Where publication times are supported, convert them to US Eastern time and
  assign after-close, weekend, and holiday items to the next trading session.
  Use the actual close, including early closes listed in the settings from the
  NYSE calendar. This is an analysis convention, not evidence that the story
  was available historically.
- Define sentiment as sentiment toward the one company a headline names. Score
  with FinBERT from local files at a pinned revision, saving the three class
  probabilities, the predicted label, and `P(positive) - P(negative)`.
- Save a daily table by company and calendar date, with article counts beside
  sentiment so sparse coverage is visible. Keep days without headlines
  distinguishable from days with neutral sentiment, and failed windows
  distinguishable from both.
- Compare with market data by Saturday-Friday week, so weekend headlines join
  the following trading week. A date-only day runs past the 16:00 close, and a
  weekly unit makes that uncertainty matter less. Three comparisons are fixed
  before scoring: for each company, the Spearman correlation between weekly
  mean score and weekly return, described as an association; for each
  shortlisted pair, the weekly score difference beside the Phase 4 unseen
  Z-scores; and a table of the five eligible Phase 4 entry signals with each
  stock's headline count and mean score over the five sessions before the
  signal. Five signals are too few for statistics. Other comparisons are added
  here before they are computed, or labelled exploratory.
- Save source snapshots, the model revision, settings, probabilities, and
  coverage and exclusion counts. Keep headline and benchmark text, prepared
  benchmark rows, and the FinBERT files out of Git, as with the raw snapshots;
  committed tables identify records by ID. The weights (438 MB) also exceed
  GitHub's file size limit. Docker reads the model folder from a read-only
  mount in offline mode. The sentiment runner is a separate command rather than
  part of the default pipeline, because a fresh clone lacks its local-only
  inputs.
- An offline rerun from saved snapshots and model files must reproduce labels,
  counts, exclusions, and classification metrics exactly. Probabilities and
  score-derived numeric diagnostics/tables must agree within an absolute
  `1e-5`. Exact floating-point equality between Windows and Linux is not
  assumed. The numeric distinction was clarified during verification:
  Docker's FiQA MAE/RMSE differed by about `3e-9` and `2e-8`,
  while its classification metrics were identical. The tolerance itself did
  not change; numeric errors derived from probabilities use the same bound.

### Pilot decision

The saved 42-company-week pilot passed the adopted rule. Apple, Microsoft,
and NVIDIA each had five usable weeks; Amazon and Alphabet had six; Meta had
four. The pilot retained 1,016 headlines without scoring them. The queries,
company names, and cleaning rules stay as adopted. Counts and exclusions are
in [the pilot report](../outputs/metrics/sentiment/sentiment_v1/pilot_report.json).

Benchmark overlap normalization uses NFKC, case folding, and Unicode word
tokens joined by spaces, so punctuation and tokenization do not hide an
otherwise equal sentence. Headline deduplication keeps the adopted NFKC,
lower-case, and single-spacing rule. A copy outside a request's intended
window is excluded before marking its GUID as seen, so it cannot hide the
valid copy in a neighbouring window.

Weekly comparisons omit incomplete study weeks as well as failed or capped
weeks. In particular, 1-2 January is not a full Saturday-Friday news week.
Weekly scores weight individual headlines rather than giving each day's mean
equal weight. These are aggregation rules, fixed before scoring the news.

A failed or capped source date also flags the next trading session, because
missing timed items after close could have been assigned there. This carries
the original source gap forward once; it does not propagate gaps recursively.
Daily outputs keep direct-request status separate from this timing uncertainty.
Saved pilot/full roles, acquisition settings, and expected windows are checked
before use. Settings that differ from the adopted sentiment thresholds are
rejected rather than silently recorded alongside hard-coded labels.

### Review corrections

A review of the first full run (`sentiment_v1`) found three rules applied
differently from their purpose. I changed them for coverage and consistency,
not because of the scores, and reran the study into `sentiment_v2`. The first
run's outputs are kept unchanged.

- **Split windows.** Cleaning had read only the final narrower requests of a
  split window. Google's results for a window and its parts do not add up: in
  42 of the 70 split windows of the full snapshot, the narrower requests
  together returned fewer items than the wider request's 100. Every saved
  successful response is now read, the narrower requests first, and an item
  returned more than once is kept once. Leaf requests still decide
  completeness and capped flags; the wider responses only add items. The full
  study retains 5,715 headlines instead of 3,846. The pilot recount retains
  1,287 instead of 1,016 with the same usable weeks for every company, so the
  pilot decision stands; see the
  [corrected pilot report](../outputs/metrics/sentiment/sentiment_v2/pilot_report.json).
- **Repeated benchmark text.** FiQA lists one headline under two IDs, each
  annotating a different target. Keeping the first copy treated a two-target
  headline as a single-annotation record. Both copies are now excluded.
- **Short PhraseBank entries.** Three FinEntity paragraphs had been excluded
  for containing a PhraseBank entry of one to three words. An entry that short
  does not show that the paragraph was in FinBERT's fine-tuning data, and the
  adopted check already keeps text that shares only a few words with a
  sentence. Containment now needs at least five words. On this data, any
  limit of four words or more gives the same result.

### Open items

- The corrected study is implemented and reproduced locally and in Docker.
  Findings and verification are in
  [sentiment analysis](phase_planning/sentiment_analysis.md).
- Phase 6 does not display the saved results (see the next section).
  Submission packaging must settle access to the local-only snapshots and
  model files; a later RSS search cannot reproduce the same news sample by
  itself.

## API and web application

### Frameworks (Adopted)

- **API: FastAPI.** Pydantic request validation, routing, and model loading at
  startup cover the required service functions. Its generated `/docs` page
  shows the routes, and its test client supports API tests. Flask would need a
  separate validation library; Django REST Framework is built for database-backed
  applications; model-serving platforms such as BentoML add packaging beyond
  this project's needs.
- **Interface: Streamlit.** The interface needs a file upload, a few inputs,
  result tables, and line charts of the spread and Z-scores, all of which
  Streamlit provides in plain Python with little code. Dash offers finer layout
  control at roughly two to three times the code; Gradio suits single
  input-to-prediction demos better than a page of test results and charts.
  (Rationale revised for the flow below; the choice is unchanged.)
- **Rule:** the Streamlit app reaches models only through the API over HTTP.
  It never loads model artifacts directly, so the interface-to-API-to-model
  path is what gets tested. The service does every calculation; the interface
  only sends requests and draws the responses.
- **Deployment:** local Docker first. Hosting is Open; a public URL is claimed
  only if verified.

### Docker runtime (Adopted)

One Dockerfile builds one image holding all project code and the locked
dependencies. Its default command runs the batch phases in order, each phase
reading the files the previous one wrote inside the same container. Single
phases can still be run by passing their script as the command. The API and
the Streamlit app run as two containers started from the same image with
different commands, through one Compose file, because both are long-running
servers and the app reaches the API over HTTP.

The image never contains `data/interim`, `data/processed`, or `outputs` from
the workstation. Every batch run rebuilds derived data from the raw
snapshots, so a result that exists only on the workstation, or a script that
fails without writing its file, cannot pass the Docker check. The serving
containers read saved files instead; see
[Serving containers](#serving-containers-adopted). IBKR data are
excluded for licensing reasons.

### Price input and cointegration test (Adopted)

The application tests one pair on prices the user supplies. The user either
uploads one CSV file, with a `Date` column and one column of closing prices
per stock headed by its ticker, or loads the project's own closing prices for
one of the 15 pairs. Both reach the same API route as a price table, so the
analysis never reads project files itself. The API rejects a request rather
than repairing it when dates repeat, are out of order, or fail to parse, when a
price is missing, non-positive, or non-finite, or when the two tickers are the
same. Prices are not fetched from a provider at request time: the same request
could then return different results, and the application would stop working
whenever Yahoo was unreachable.

The user chooses a fit end date, which defaults to 2025-12-31 for the
project's prices. At least 504 sessions must fall on or before it and at least
20 after it. The data up to the fit end go through the Phase 3 procedure with
the Phase 3 settings: OLS on log prices in both directions with an
Engle-Granger test of each, and a Johansen trace test. The direction with the
smaller Engle-Granger p-value defines the spread. The pair counts as
cointegrated when the direction-adjusted p-value, `min(1, 2 * smaller
directional p)`, is at most 0.05 and the trace test gives rank one at 95%. The
I(1) checks on each stock are reported as warnings and do not decide the
result.

There is no correction across pairs. Phase 3 searched all 15 pairs and applied
Holm's correction to that search, whereas here the user names one pair before
it is tested. On the project's prices with a 2025-12-31 fit end, AMZN_META
passes (direction-adjusted p 0.0284; trace statistic 17.60 against 15.49)
although Phase 3 labelled it exploratory, and NVDA_AMZN fails both tests.
Choosing AMZN_META because Phase 3 ranked it first is itself a search, so its
single-pair p-value overstates the evidence. The application says so beside
the result for any of the 15 project pairs.

### Spread, Z-scores, and signals (Adopted)

The spread's mean and sample standard deviation (`ddof=1`) come from the final
year of the fitting window: the sessions later than the same calendar date one
year before the fit end. With a 2025-12-31 fit end this is Phase 4's 2025
window of 250 sessions. The regression and normalization stay fixed for the
sessions after the fit end. Z-scores up to the fit end are returned as
in-sample context.

Signals follow the [Phase 4 trading rules](#trading-rules-adopted)
unchanged, over the sessions after the fit end. The run starts flat, and the
last Z-score of the fitting window serves only as the comparison for the first
later session. The response gives dated signals and long and short counts,
counted as in Phase 4. It includes no P&L backtest; Phase 4 already reports
one for the project pairs.

When the pair fails the test, the response carries the test results only. The
user can request an exploratory view, which returns the spread, Z-scores, and
signals labelled exploratory, in the same way the
[weak-evidence rule](#pair-handling-when-evidence-is-weak-adopted) carried the
Phase 3 shortlist forward.

Phase 4's `fit_normalization` accepts only 2025 residuals, and the Phase 4 and
Phase 5 evaluation contracts hash the trading, features, and models code. The
window calculation is therefore new code under `src/market_analytics/api/`,
which imports the Phase 3-5 functions without editing them. Run on the
project's AMZN_META prices with a 2025-12-31 fit end, it must reproduce the
saved Phase 4 unseen Z-scores and signal counts.

### Saved-model forecasts and routes (Adopted)

A separate route serves the saved `phase5_v2` LSTM bundles for AMZN_META and
NVDA_AMZN through `forecast_from_prices`. At startup the API reproduces each
bundle's saved example forecast; the function then rereads the small bundle on
every request. Each bundle carries its own 2018-2025 regression and 2025
normalization, which the route uses instead of the user's fit, so the
interface shows forecasts apart from the test results. A request needs at
least 39 consecutive sessions of closing prices ending at the forecast origin:
the 20-session input window plus the 19 earlier sessions its first rolling
standard deviation needs. The interface notes that persistence beat both
models on the unseen period at every horizon.

Forecast origins must fall on or before 2026-07-31, the last session in the
project's masters. `forecast_from_prices` checks the supplied dates against an
independent calendar so that a missing session cannot pass unnoticed, and the
project's own dates are that calendar. Later origins would need an exchange
calendar library, which nothing in the project requires. Target dates after
2026-07-31 are returned as horizons without dates.

- `GET /health`: service status and the loaded bundle versions.
- `GET /pairs`: the six tickers, the 15 pairs with their Phase 3 labels, and
  which pairs have a saved LSTM bundle.
- `GET /samples/{pair}`: the project's closing prices for a pair from
  2018-01-02 to 2026-07-31, in the upload format.
- `POST /analyze`: prices, fit end, and the exploratory flag. Returns the test
  results and, when allowed, the regression, normalization, spread, Z-scores,
  and signals.
- `POST /forecast`: a pair with a saved bundle and its closing prices. Returns
  five forecasts, dated where the project calendar reaches, and whether the
  day-five forecast moves toward zero, the condition the Phase 5 filter uses.

The application is a demonstration on historical prices, not a trading tool.

### Serving containers (Adopted)

The API and app containers start from the batch image with different
commands. They read `artifacts/lstm/phase5_v2/`, `data/processed/`, and
`outputs/metrics/pair_selection/` from read-only mounts of the project folder.
The image itself still excludes these folders, so the batch pipeline keeps
rebuilding everything from the raw snapshots.

The forecasts served therefore match the reported Windows results: Phase 5's
Docker check reloaded those weights on Linux within 1.49e-8. Retraining inside
the API container would move them by up to 0.017 Z and take minutes at every
start. Copying the saved files into the image would also put them in
the batch image. The mounts need the project folder, which is present for
local use and in the submission archive. A hosted deployment would need
another way to supply these files.

### Sentiment in the application

The interface has no sentiment page and the API no
sentiment route. The study's results are mixed. FinBERT beats VADER on both
benchmarks, but its FinEntity accuracy is below a constant neutral reference,
and almost all collected headlines carry dates without times, so they cannot
be placed before or after a session's close. That supports reporting the
study on its own. It does not support feeding the scores into signals or
showing them next to the pair analysis, where they would read as an input to
it. The study stays in its notebook and in the report as a separate
experiment.

## References

These support the choices above; check behavior against the installed library
versions when implementing.

- [Statsmodels Engle-Granger test](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.coint.html):
  cointegration inference, integration assumptions, and regression/lag settings.
- [Statsmodels Johansen test](https://www.statsmodels.org/stable/generated/statsmodels.tsa.vector_ar.vecm.coint_johansen.html):
  deterministic terms, lag specification, test statistics, and critical values.
- [Statsmodels ADF test](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html):
  integration diagnostics, deterministic terms, maximum lags, and autolag.
- [Statsmodels VAR lag selection](https://www.statsmodels.org/stable/generated/statsmodels.tsa.vector_ar.var_model.VAR.select_order.html):
  information-criterion curves for the Johansen lag choice.
- [Statsmodels multiple-testing correction](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html):
  Holm-adjusted p-values alongside the nominal directional tests.
- [Scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html):
  fitting preprocessing on training data and preventing evaluation leakage.
- [FinBERT model card](https://huggingface.co/ProsusAI/finbert): model
  description, label order, training data, and licence.
- [Financial PhraseBank dataset card](https://huggingface.co/datasets/takala/financial_phrasebank):
  the overlap-screen files and their licence.
- [VADER](https://github.com/cjhutto/vaderSentiment): the rule-based comparison
  and its recommended compound-score thresholds.
- [GNews documentation](https://github.com/ranahaani/GNews#results-specification):
  Google News RSS language, region, date, and result-count settings. The
  collector reads the feed directly rather than through this package.
