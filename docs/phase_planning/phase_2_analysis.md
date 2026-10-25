# Phase 2 analysis: exploring the historical data

25 October 2026

This note reports what the exploratory analysis found for the six stocks and
the S&P 500 over 2018-2025. The only input is
`data/processed/master_historical.csv`; the unseen 2026 data were not opened.
The methods were adopted in the [methodology](../methodology.md#phase-2-exploratory-analysis)
before any number here was calculated, and none of them was varied afterwards.
Every number below comes from the tables in `outputs/metrics/eda/` or is
read off the figures in `outputs/figures/eda/`. The run is logged as EXP-001 in
the [experiment log](../experiment_log.md).

These are descriptions of the past, not out-of-sample results. All 15 pairs go
on to Phase 3 whatever their correlation, and nothing here is evidence of
cointegration.

## How the run was checked

The run checks the master's SHA-256 against the Phase 1 manifest before
reading it, and stops on any missing value other than the seven returns on
2018-01-02. It then recalculates its own results in a second way: compounded
returns against the ratio of Closes (63 cases), every beta against
covariance/variance and R-squared against squared correlation (54
regressions), and 45 rolling windows against a direct calculation on their 60
returns, where the largest gap was 5.7e-15. All 22 checks are listed in
`run_metadata.json`.

Two library behaviours needed handling. For a window of constant returns,
pandas 3.0.6 returns `inf` from `Rolling.corr` instead of a missing value, and
statsmodels returns a beta with only a warning when the benchmark is constant.
Neither happens in the real data, but the code detects constant inputs itself
and the tests cover both cases.

I repeated the run in Docker by rebuilding the historical master from the raw
snapshots and running the EDA on it. The rebuilt master has the same hash as
the Windows file, five tables are byte-identical, and the other five differ by
at most 1.3e-15 ([validation record](../../outputs/metrics/phase2_docker_validation.json)).

## Return and risk

Source: [`stock_summary.csv`](../../outputs/metrics/eda/stock_summary.csv),
[`stock_annual_summary.csv`](../../outputs/metrics/eda/stock_annual_summary.csv),
figures `performance_index.png` and `drawdowns.png`.

| Instrument | Compounded return | Annualized volatility | Maximum drawdown | Peak to trough |
| --- | --- | --- | --- | --- |
| MSFT | 462.7% | 28.4% | -37.6% | 2021-11-19 to 2022-11-03 |
| GOOGL | 483.3% | 31.0% | -44.3% | 2021-11-18 to 2022-11-03 |
| NVDA | 3,642.2% | 51.3% | -66.4% | 2021-11-29 to 2022-10-14 |
| AAPL | 531.3% | 30.8% | -38.7% | 2018-10-03 to 2019-01-03 |
| AMZN | 288.3% | 34.4% | -56.1% | 2021-07-08 to 2022-12-28 |
| META | 263.8% | 41.4% | -76.7% | 2021-09-07 to 2022-11-03 |
| S&P 500 | 153.9% | 19.6% | -33.9% | 2020-02-19 to 2020-03-23 |

These are price returns for the stocks and the benchmark; dividends are
excluded under the Phase 1 price policy.

NVDA dominates the period: its Close rose by a factor of about 37, eight times
MSFT's percentage gain, and it also had the highest volatility. All six stocks
beat the S&P 500 on price return over the full period. Each stock was also
more volatile than the index in every calendar year. Return and risk did not line up neatly among the stocks,
though. META was the second most volatile but had the lowest return and the
deepest drawdown, while MSFT was the least volatile stock and still returned
463%.

The large losses cluster in one episode. Five stocks reached their deepest
point between October and December 2022, and 2022 is the only year in which
all seven series fell (from -19.4% for the index to -64.2% for META). The
following year had the largest rebounds: NVDA +238.9% and META +194.1%. AAPL
is the exception, with its worst fall in late 2018, and the index's worst fall
was the five weeks of the 2020 crash.

## Pair correlations

Source: [`pair_correlations.csv`](../../outputs/metrics/eda/pair_correlations.csv),
[`return_correlation_matrix.csv`](../../outputs/metrics/eda/return_correlation_matrix.csv),
figures `return_correlation_heatmap.png`, `pair_log_prices.png`, and
`pair_return_scatter.png`.

Daily-return correlations are positive for all 15 pairs, between 0.525
(NVDA_META) and 0.708 (MSFT_GOOGL), each from 2,010 same-day observations.
MSFT is in the four most correlated pairs (with GOOGL 0.708, AAPL 0.700, AMZN
0.682, and NVDA 0.661). The pairs with META or NVDA are at the bottom: the five
lowest are NVDA_META, AAPL_META, NVDA_AAPL, GOOGL_NVDA, and NVDA_AMZN. The
scatterplots show the same thing as tight clouds for MSFT pairs and wider
ones with more isolated large moves for META and NVDA.

Correlation of log price levels is higher than return correlation for every
pair, from 0.728 (AAPL_META) to 0.977 (MSFT_AAPL). All six stocks trended
upwards over the period. MSFT_NVDA has a level correlation of
0.938 even though NVDA's price rose about eight times as much as MSFT's in
percentage terms, and the rebased log-price panel shows the two lines drifting
apart after 2023. These panels compare the two log prices with equal weights.
Phase 3 estimates an intercept and hedge ratio before testing the residual
spread, so separation of the unweighted lines alone cannot settle whether
that fitted spread is stationary.

## Sensitivity to the S&P 500

Source: [`benchmark_sensitivity.csv`](../../outputs/metrics/eda/benchmark_sensitivity.csv),
figure `benchmark_scatter.png`.

| Stock | Beta | R-squared | Lowest annual beta | Highest annual beta |
| --- | --- | --- | --- | --- |
| MSFT | 1.18 | 0.66 | 0.91 (2025) | 1.45 (2018) |
| GOOGL | 1.16 | 0.53 | 0.95 (2020) | 1.38 (2023) |
| NVDA | 1.82 | 0.48 | 1.33 (2020) | 2.67 (2024) |
| AAPL | 1.22 | 0.60 | 0.96 (2024) | 1.56 (2019) |
| AMZN | 1.18 | 0.45 | 0.68 (2020) | 1.64 (2022) |
| META | 1.32 | 0.39 | 0.99 (2020) | 1.77 (2023) |

Every stock had a whole-period beta above 1: on average each moved more than
one-for-one with the index. NVDA is the most sensitive, with a beta of 1.82.
How much of a stock's daily movement the index explains is a separate
question. MSFT's R-squared is 0.66, while META's is 0.39, so most of META's
daily variation is not explained by the market. Daily alphas are small (0.03%
to 0.13% per day) and are not evidence of anything beyond the period's price
gains.

Betas changed from year to year. NVDA's doubled between 2020 and 2024. 2020
gave the lowest annual beta for four stocks, AMZN, GOOGL, META, and NVDA, even
though the market fell and recovered sharply that year. For GOOGL and META,
2020 also had the highest R-squared of any year. In the crash year those
stocks followed the index more closely in the fitted regressions, but by less
than one percentage point of stock return per percentage point of index
return. A single whole-period beta therefore hides a lot of variation.

## Stability over time

Source: [`pair_annual_correlations.csv`](../../outputs/metrics/eda/pair_annual_correlations.csv),
[`rolling_correlations.csv`](../../outputs/metrics/eda/rolling_correlations.csv),
figures `pair_annual_correlation_heatmap.png` and `rolling_correlations.png`.

Correlations rose and fell together across pairs. They were highest in 2020
(0.67 to 0.86 across the 15 pairs) and 2022 (0.59 to 0.85) and lowest in 2024
(0.23 to 0.69). The 60-session rolling correlations show larger swings than
the annual ones: every pair had at least one window below 0.30, and 16
windows across three pairs (MSFT_AAPL, AAPL_AMZN, NVDA_AAPL) were slightly
negative, the lowest -0.040 for NVDA_AAPL in the window ending 2025-01-27. The
highest window was 0.952 for MSFT_AAPL, ending 2020-05-14.

The end of 2025 matters most for what comes next, because Phase 4 uses 2025
to normalize the spreads. In the window ending 2025-12-31, 11 of the 15 pairs
were below 0.40, and MSFT_GOOGL, the most correlated pair over the eight
years at 0.708, was at 0.06. Its 2025 annual correlation, 0.42, was its lowest
of any year. So the relationships the whole period suggests were weaker in
the final year.

## VIX context

Source: [`vix_group_stock_summary.csv`](../../outputs/metrics/eda/vix_group_stock_summary.csv),
[`vix_group_pair_correlations.csv`](../../outputs/metrics/eda/vix_group_pair_correlations.csv),
[`vix_group_year_counts.csv`](../../outputs/metrics/eda/vix_group_year_counts.csv),
figure `vix_timeline.png`.

The one-third and two-thirds quantiles of the VIX close over the 2,010 return
dates are 15.93 and 20.743. They split the dates into 672 low, 668 medium,
and 670 high-VIX days.

Volatility rose from the low to the high group for all seven series. The S&P
500's daily standard deviation went from 0.54% to 1.87%, a factor of 3.45. For
the stocks the factor was smaller, from 1.70 for GOOGL to 2.27 for MSFT,
because their volatility on calm days was already high. Correlation also rose
with VIX for every one of the 15 pairs, from 0.20-0.54 in the low group to
0.65-0.84 in the high group. On high-VIX days the six stocks moved together
much more, which fits the annual results for 2020 and 2022.

The year counts limit this result. 435 of the 670 high-VIX dates are in 2020
and 2022, and 2022 had no low-VIX dates at all. The comparison therefore
largely contrasts two stressed years with calm years such as 2019 and 2024,
and I cannot separate the effect of VIX level from the particular events of
those years. It shows an association in this sample, not that VIX causes
higher volatility or correlation. VIX is not added to the trading rules or the
LSTM because of this.

## Limitations

- Returns exclude dividends for both the stocks and the S&P 500 benchmark.
  The results describe price performance rather than total return.
- High-VIX observations are concentrated in 2020 and 2022. Several results,
  including the VIX comparison, depend heavily on those two years.
- Correlation and beta are linear measures of same-day co-movement. They miss
  lagged effects and do not describe the gap between two prices, which is
  what pair trading depends on.
- The VIX boundaries were estimated on the dates they describe. That is fine
  for description, but they could not be used as trading thresholds without
  refitting on a training window.
- The 60-session window is one choice made in advance. A shorter window would
  show more short-lived swings and a longer one fewer; I did not test
  alternatives, to avoid choosing the one that looks best.

## What this means for Phase 3

All 15 pairs have positive daily-return correlations, ranging from 0.525 to
0.708 over the full period, with substantial changes over time. MSFT appears
in the four highest-correlated pairs, while NVDA or META appears in the five
lowest. These results describe same-day returns; they do not rank the evidence
for cointegration. Unequal growth in the rebased log-price plots can be
consistent with a hedge ratio other than one. Phase 3 will fit the log-price
relationships and assess cointegration evidence for all 15 pairs using
Engle-Granger and Johansen tests.

Code corrections made after review, which left every table unchanged, are
recorded in [EXP-002](../experiment_log.md#exp-002--2026-10-25--phase-2-review-and-rerun).
