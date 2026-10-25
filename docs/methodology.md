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

| Date | Area | Decision | Status |
| --- | --- | --- | --- |
| 2026-10-25 | Phase 2 scope | Compare return and risk, cover all 15 pairs and benchmark sensitivity, examine relationships by year and with rolling correlations, and add VIX context | Adopted |
| 2026-10-25 | Phase 2 methods | Pearson return and log-price correlations, return/risk definitions, OLS beta with intercept, 60-session rolling window, VIX terciles | Adopted |
| 2026-10-25 | Docker runtime | One image; ordered batch pipeline as the default command; API and app as two containers from that image | Adopted |
| 2026-10-25 | LSTM device | CPU-only PyTorch build; final models and reported metrics produced on CPU | Adopted |
| 2026-10-25 | Build reproducibility | Verify only selected Yahoo periods; slice shared Cboe history before price checks; omit wall-clock time from the build manifest | Adopted |
| 2026-10-24 | Data sources | VIX close from Cboe; stocks and S&P 500 from Yahoo; IBKR used only to check Yahoo | Adopted |
| 2026-10-24 | Master layout | Column set, hard stops instead of filling, 15% move flag, `\n` line endings | Adopted |
| 2026-10-18 | Prices | Close drives returns, spreads, and P&L; dividends are omitted and documented | Adopted |
| 2026-10-18 | Calendar fields | Master stores integer Year, Quarter, and Month; each analysis encodes them as needed | Adopted |
| 2026-10-18 | Pair selection | If no pair qualifies, carry forward the strongest candidates labelled exploratory | Adopted |
| 2026-10-18 | LSTM splits | Select on 2018-2023 training / 2024-2025 validation, then refit through 2025 | Adopted |
| 2026-10-18 | Execution | Signal after the close on day t; fill at the open on day t+1 | Adopted |
| 2026-10-18 | LSTM framework | PyTorch | Adopted |
| 2026-10-18 | Sentiment | Google News headlines scored locally with FinBERT; standalone descriptive study | Adopted |
| 2026-10-18 | API and app | FastAPI API; Streamlit interface calling it over HTTP; local Docker first | Adopted |

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
time in October 2026. Its historical values therefore include dividends paid in
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

### Scope (Adopted 2026-10-25)

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

### Return and risk measures (Adopted 2026-10-25)

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

### Pair relationships (Adopted 2026-10-25)

Use Pearson correlation of same-day daily returns as the main comparison.
Save all 15 unique unordered pairs, their sample counts, and a six-stock
correlation matrix. Each pair gets a time-series panel of
`log(Close_t / Close_first)` and a scatterplot of the two daily returns.
The former is in natural-log units; the latter uses percentage returns.

Also report Pearson correlation of the log-price levels in the pair table,
labelled separately from return correlation. This comparison illustrates how
similar trends can produce high level correlations without establishing a
stable equilibrium. Neither measure is evidence of cointegration.

### Benchmark sensitivity (Adopted 2026-10-25)

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

### Relationship stability (Adopted 2026-10-25)

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

### VIX context (Adopted 2026-10-25)

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

The methods above were reviewed and adopted on 2026-10-25, before any of them
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

### Test design (Proposed)

The following settings are fixed before results are examined:

- **Integration check:** ADF on each log-price series (with a trend term) and
  on its first differences, to assess whether each is plausibly I(1). A series
  that appears trend-stationary weakens cointegration conclusions for its pairs.
- **Regressions:** `log(A) = intercept + beta * log(B) + residual` over the
  historical period, in both directions for all 15 pairs (30 regressions). All
  results are kept, not only the selected ones.
- **Engle-Granger:** `statsmodels.tsa.stattools.coint` with a constant is the
  main residual-based test. A plain ADF p-value on fitted OLS residuals is not
  used for inference: OLS chooses the coefficients that make the residuals look
  most stationary, so standard Dickey-Fuller critical values are too lenient.
  `coint` uses MacKinnon critical values appropriate for this case. The
  direction with the lower p-value is selected.
- **Johansen:** `coint_johansen` with `det_order=0`, consistent with the
  constant in the Engle-Granger regressions. Lag order comes from a VAR
  information criterion. Trace and maximum-eigenvalue statistics are reported
  against the 90%, 95%, and 99% critical values with the inferred rank. The
  implementation does not supply p-values and none are invented.
- **Significance level:** 5%.
- **Ranking:** primary order by the selected-direction Engle-Granger p-value,
  with the Johansen trace test at 95% as confirmation. Pairs are grouped as
  supported by both methods, by one method, or by neither.
- **Shortlist:** two to three pairs, with the reason for each.
- **Supporting diagnostics:** half-life of mean reversion and stability of the
  hedge ratio between 2018-2021 and 2022-2025. These inform interpretation, not
  the ranking.

With 15 pairs tested at 5%, about 0.75 false positives are expected even if no
pair is truly cointegrated. The report discusses this multiple-testing effect.

The selected spread is saved with its orientation and coefficients so later
phases can reconstruct it as `log(price A) - intercept - beta * log(price B)`.

## Phase 4: Statistical baseline

### Spread and normalization (Proposed)

The Phase 3 regression fitted on 2018-2025 defines the spread. Its residual
mean and standard deviation are estimated over 2025 only. The unseen Z-score is

`Z(t) = (spread(t) - mean_2025) / std_2025`

using the sample standard deviation (`ddof=1`). A zero or non-finite standard
deviation stops the run with an error. Neither the regression nor the
normalization parameters are refitted on 2026.

### Trading rules (Proposed)

- Long the spread when Z falls below -2; exit when Z reaches 0 or above.
- Short the spread when Z rises above +2; exit when Z reaches 0 or below.
- Thresholds are fixed in advance and are not tuned on unseen outcomes.
- Entries trigger on a threshold crossing while flat. Repeated signals while a
  position is open are ignored.
- If an exit and an opposite entry occur on the same day, the exit is executed
  and a new entry requires a fresh crossing on a later day.

### Execution and accounting (Adopted timing; Proposed accounting)

- **Timing (Adopted):** signals are computed after the close on day t and
  executed at the open on day t+1. Exits follow the same rule. The equity curve
  is marked at each close. Overnight gaps between close and next open are part
  of the result.
- **Holdings:** share quantities are fixed at entry: notional N in the
  dependent stock and beta times N in the other, converted to shares at the
  execution prices. Cash P&L comes from shares and price changes. The log-price
  coefficient is an elasticity, not a share ratio, and the change in a log
  spread is not itself a cash profit.
- **Return denominator:** gross notional at entry, N times (1 + |beta|).
- **Costs:** 5 basis points per leg per transaction, with gross (zero-cost)
  results also reported. Short-borrow fees, financing, and dividends are
  omitted and listed as limitations.
- **Open positions:** a position still open on 2026-07-31 is marked at that
  close, flagged as open, included in returns, and excluded from win rate.
- **Metrics:** long and short entry signals, executed trades, closed trades,
  win rate (closed trades with positive net P&L), total and average trade
  return, holding period, maximum drawdown, and gross versus net performance.
  Signal counts are reported separately from executed trades.
- **Historical run:** the strategy is also run on historical data to check the
  accounting. Those results are labelled in-sample because the parameters were
  fitted on the same period.

The 2025-only normalization centers Z on the most recent equilibrium. If the
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

The final refit has no validation set. It trains for the epoch count selected
in the selection stage. Its unseen Z-scores are identical to Phase 4's, so both
strategies trade the same series and no scale conversion is needed.

### Inputs and targets (Adopted structure; Proposed window)

- Features per day, in order: Z, Z lag 1, lag 2, lag 3, and trailing rolling
  standard deviation of Z. The rolling window length is Proposed at 20 trading
  days. The lags overlap with the 20-day sequence itself; they are included as
  specified features and this redundancy is noted.
- An origin after the close on day t uses the 20 trading days ending at t and
  predicts Z for t+1 through t+5.
- Training samples whose target window crosses into a later split are dropped.
  Earlier observations may supply input context to later splits.
- Unseen origins run from 2025-12-31 to the last origin with a complete
  five-day target. The origin count is reported.
- Any feature scaler is fitted on the training portion only and saved.

### Model (Adopted framework; Proposed design)

PyTorch was chosen for explicit control over the training loop, early
stopping, and the final-refit epoch rule. Models are saved as `.pt` files with
metadata: pair, feature order, window lengths, split dates, seed, training
device, and library versions. The starting design is one compact LSTM per selected pair (one layer,
about 32 units, five outputs, MSE loss, Adam, early stopping on validation),
with a small recorded set of experiments and fixed seeds. Unsuccessful trials
are recorded.

### Training device (Adopted 2026-10-25)

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

### Evaluation (Proposed)

MAE and RMSE are reported for each horizon from 1 to 5, plus a defined
aggregate, with sample counts. A persistence forecast that repeats the latest
observed Z at every horizon is evaluated on the same origins and targets; an
AR(1) forecast may be added. Z-scores are highly autocorrelated, so persistence
is a demanding benchmark at short horizons. Forecast quality is assessed
separately from trading results.

### LSTM-enhanced strategy (Proposed)

The forecast filters statistical entries: a Phase 4 entry is taken only when
the forecast indicates movement toward equilibrium (for a long, forecast Z at
the chosen horizon above current Z). The horizon, aggregation, and any
threshold are set on 2024-2025 validation. The strategy uses the Phase 4
backtest function, execution timing, notional, costs, and metric definitions.
Both strategies' rules are frozen before the 2026 comparison, and the
baseline's 2026 results are not used to tune the LSTM strategy.

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

### Procedure (Proposed)

- Run a small collection pilot first to establish usable coverage; the target
  window is January-July 2026, adjusted to the pilot's findings. RSS results are
  limited, so completeness is checked rather than assumed.
- Collect through the `gnews` package or the RSS feeds directly.
- Remove irrelevant name matches and duplicate or syndicated headlines.
- Convert publication times to US Eastern time; a headline published after the
  16:00 close is assigned to the next trading day.
- Define sentiment as sentiment toward the named company, with a written
  labelling guide covering headlines that mention several companies.
- Hand-label 150-300 headlines across companies and dates. The project author
  does the labelling so the evaluation is independent of the model and the
  assistant. FinBERT is not fine-tuned, so the whole labelled set is evaluation
  data.
- Report class counts, macro-F1, a confusion matrix, and representative errors,
  with VADER and a majority-class rule as comparison baselines.
- Show article counts alongside sentiment so sparse coverage is visible.
- Save the source snapshot and model version.

### Open items

- FinBERT licence terms are checked against the model card before use and
  recorded with the citation.

## API and web application

### Frameworks (Adopted)

- **API: FastAPI.** Pydantic request validation, routing, and model loading at
  startup cover the required service functions. Its generated `/docs` page
  shows the routes, and its test client supports API tests. Flask would need a
  separate validation library; Django REST Framework is built for database-backed
  applications; model-serving platforms such as BentoML add packaging beyond
  this project's needs.
- **Interface: Streamlit.** The application mainly presents saved analysis plus
  one live prediction flow, which Streamlit handles in plain Python with little
  code. Dash offers finer layout control at roughly two to three times the code;
  Gradio suits single input-to-prediction demos better than a multi-view
  dashboard.
- **Rule:** the Streamlit app reaches models only through the API over HTTP.
  It never loads model artifacts directly, so the interface-to-API-to-model
  path is what gets tested.
- **Deployment:** local Docker first. Hosting is Open; a public URL is claimed
  only if verified.

### Docker runtime (Adopted 2026-10-25)

One Dockerfile builds one image holding all project code and the locked
dependencies. Its default command runs the batch phases in order, each phase
reading the files the previous one wrote inside the same container. Single
phases can still be run by passing their script as the command. The API and
the Streamlit app run as two containers started from the same image with
different commands, through one Compose file, because both are long-running
servers and the app reaches the API over HTTP.

The image never contains `data/interim`, `data/processed`, or `outputs` from
the workstation. Every container run rebuilds derived data from the raw
snapshots, so a result that exists only on the workstation, or a script that
fails without writing its file, cannot pass the Docker check. IBKR data are
excluded for licensing reasons.

### Routes and user flow (Proposed)

Routes: `GET /health`, `GET /pairs`, `GET /pairs/{pair}/zscores`,
`POST /predict`, and `GET /backtests/{pair}`. The app lets a user select a pair,
inspect its selection evidence, view its spread and dated forecasts, and compare
both strategies, with a separate sentiment view. The scope is a clearly dated
historical demonstration, not live trading.

## References

These support the choices above; check behavior against the installed library
versions when implementing.

- [Statsmodels Engle-Granger test](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.coint.html):
  cointegration inference, integration assumptions, and regression/lag settings.
- [Statsmodels Johansen test](https://www.statsmodels.org/stable/generated/statsmodels.tsa.vector_ar.vecm.coint_johansen.html):
  deterministic terms, lag specification, test statistics, and critical values.
- [Scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html):
  fitting preprocessing on training data and preventing evaluation leakage.
- [FinBERT model card](https://huggingface.co/ProsusAI/finbert): model
  description and licence, to be confirmed before use.
- [gnews package](https://pypi.org/project/gnews/): Google News RSS access
  without an API key.
