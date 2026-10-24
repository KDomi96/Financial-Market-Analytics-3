# Phase 1 analysis: checking the market data

24 October 2026

Yahoo Finance is the project's market data source. Before building the master
dataset I checked the Yahoo download against two independent references:
daily bars from Interactive Brokers (IBKR), and Cboe's official VIX history.
Yahoo held up for the six stocks and the S&P 500. Its VIX was wrong on three
days, so VIX is taken from Cboe. This note shows the comparison and the
reasoning behind that outcome.

## What was compared

| Source | Snapshot | Fields | How it was obtained |
| --- | --- | --- | --- |
| Yahoo Finance | `data/raw/yahoo_finance/20261017T112037944190Z/` | OHLC, Adj Close, volume, dividends, splits | `scripts/download_yahoo.py` (yfinance) |
| IBKR | `data/raw/ibkr/20261024T163751761776Z/` | OHLC, volume, VWAP, trade count | `scripts/download_ibkr.py`, daily `TRADES` bars through a read-only IB Gateway session |
| Cboe | `data/raw/cboe/20261024T163804809102Z/` | VIX OHLC from 1990 | `scripts/download_cboe.py`, Cboe's published CSV saved unchanged |

The comparison covers only the formal periods: 2018-01-02 to 2025-12-31 and
2026-01-02 to 2026-07-31. It was produced by `scripts/compare_sources.py`, and
every number below comes from the tables in
`outputs/metrics/source_comparison/`. For the unseen period I only compared
values between sources. Nothing was analysed for returns or trading.

A few things about IBKR's data are worth knowing before reading the results.
According to IBKR's API documentation, `TRADES` bars are adjusted for splits
but not dividends, which is the same treatment as Yahoo's `Close`. IBKR also
filters some trade types, so its volume is expected to be lower than a full
consolidated feed. The API has no start date, only an end time and a duration.
Asking for exactly "8 Y" dropped 2018-01-02, apparently because a year is
counted as 365 days and the period contains two leap days. The requests
therefore cover slightly wider windows, and the extra rows are left in the raw
files.

## Results

### Trading dates

Yahoo and IBKR have exactly the same trading dates for all eight instruments:
2,011 historical days and 145 unseen days. The only difference is VIX on
2026-05-25 (Memorial Day), which Yahoo has and IBKR does not.

Cboe explains that record. Since 30 May 2022 Cboe has published VIX on US
stock-market holidays, 27 times in the historical period and 5 times in the
unseen one, 2026-05-25 among them. These are genuine values, but stocks did
not trade on those days, so the master will not use them.

### Splits

Both sources are split-adjusted in the same way. On all five split dates
(AAPL 2020-08-31, NVDA 2021-07-20 and 2024-06-10, AMZN 2022-06-06,
GOOGL 2022-07-18) the closes before and on the split day agree, to within
Yahoo's stored precision.

### Stock closes

The closes agree almost exactly. For each of the six stocks, in both periods,
not one day differs by more than 0.1%. The largest gap is 0.073%
(AAPL on 2020-07-09), and the median gap is effectively zero. Yahoo stores its
prices at slightly lower precision, which accounts for the tiny differences on
ordinary days.

### S&P 500 close

There is one disagreement in eight years. On 2021-08-11 the two sources differ
by 0.12%. Yahoo's VIX is also wrong on that same day (see below), so Yahoo
probably has a bad record for the whole date, and IBKR's value is likely the
official close. I have not checked it against S&P Dow Jones Indices. There are
no differences in the unseen period.

### VIX close against Cboe

| Period | Source | Days compared | Days differing from Cboe | Largest difference (points) |
| --- | --- | ---: | ---: | ---: |
| Historical | Yahoo | 2,011 | 2 | 0.11 |
| Historical | IBKR | 2,011 | 28 | 2.03 |
| Unseen | Yahoo | 146 | 1 | 2.61 |
| Unseen | IBKR | 145 | 3 | 2.98 |

A day counts as differing when the gap exceeds 0.005 points, beyond Cboe's
two-decimal rounding.

Yahoo is wrong on three days: 2021-08-11 (16.17 against 16.06), 2021-10-01
(21.10 against 21.15) and 2026-02-06 (20.37 against 17.76). The last one is
off by about 15%, and it falls in the unseen period.

IBKR is wrong on 31 days. On 25 of them its close equals Cboe's value for the
next calendar day that Cboe published, and in every one of those cases that day
is a stock-market holiday (for example 2025-06-18, before Juneteenth, and
2026-01-16, before Martin Luther King Jr. Day). So IBKR's daily bar for the
last session before a holiday takes up the holiday's VIX print. Because of that
the VIX closes before holidays are unreliable in the IBKR data, which also
explains why its worst gaps to Cboe are about 2 to 3 points. I have not found
the cause of the other six days.

### Open, high and low

Open prices differ routinely between Yahoo and IBKR. For the stocks, between
38 and 143 historical days per stock differ by more than 0.1%, and single days
reach about 1% (2.5% for META on 2018-01-30). The likely reason is that one
source reports the official opening auction price and the other the first
trade. I have not established which is which. The master uses Yahoo's open,
and the strategy backtests later execute at it, so on some days a fill price
may be off by a fraction of a percent.

Yahoo has some obviously bad highs and lows. On 2025-12-12 its META high is
711.00, on a day that opened at 649.80 and closed at 644.23; IBKR's high for
that day is close to the open, about 8% below Yahoo's.
Highs and lows are kept in the master because they are part of the required
OHLC data, but no planned calculation uses them.

### Volume

IBKR's stock volume is 49–72% of Yahoo's, by median per stock and period,
with single days as low as 18%. This is the filtering described in IBKR's
documentation, not an error. Yahoo's figure is closer to total market volume.

## Outcome

| Series | Source in the master | Evidence |
| --- | --- | --- |
| Six stocks: OHLC, volume | Yahoo | Closes match IBKR within 0.1% on every day; splits handled identically |
| S&P 500 close | Yahoo | Matches IBKR on every day but one (2021-08-11, 0.12%) |
| VIX close | Cboe | Cboe calculates the index; Yahoo is wrong on three days, one of them in the unseen period |

IBKR's role was to check Yahoo, not to replace it, and nothing from IBKR goes
into the master. The main result of the check is that Yahoo's closes, which
drive returns, spreads, and P&L, agree with an independent broker feed on
every trading day. IBKR is a weaker reference for VIX (31 days off against
Cboe) and for volume (filtered by design), so for those fields the comparison
says more about IBKR than about Yahoo.

Where IBKR points to a likely Yahoo error, the S&P 500 close on 2021-08-11, I
kept Yahoo's value rather than substituting IBKR's. The error is small, lies
outside the unseen period, and affects only two daily returns (2021-08-11 and
2021-08-12) by about 0.12 percentage points each. Patching single values from
a second provider would make the series harder to reproduce and explain than
the error is worth. It is recorded as a known limitation.

VIX is a different case. The Yahoo error on 2026-02-06 is large, and it falls
in the evaluation period. VIX enters the master as a level, so nothing smooths
the error away. Cboe is the official source, is free, and needs no account, so
the whole series is taken from Cboe, not patched.

## Availability of the IBKR data

Nothing from IBKR is in the public repository. IBKR's subscriber agreement
does not allow its market data to be reproduced or distributed without written
consent (see [data sources](../data_sources.md#interactive-brokers-cross-check-only)
for the clause). A reviewer therefore cannot rerun the IBKR comparison from the
repository alone: it needs an IBKR account with US stock and Cboe index data,
and `scripts/download_ibkr.py` then recreates the snapshot. The Yahoo and Cboe
comparisons can be rerun from the committed files. The comparison tables in
`outputs/metrics/source_comparison/` are the record of what the check found;
for IBKR they hold only summary statistics, counts, dates, and yes/no flags,
and the figures quoted in this note are differences, not IBKR prices.

## Limitations

The chosen data carry three known weaknesses. Yahoo's S&P 500 close on
2021-08-11 is probably wrong by 0.12%, which slightly distorts two daily
returns. Yahoo's open may not be the official opening auction price, which
matters only where trades execute at the open. Some of Yahoo's highs and lows
are bad prints, but no planned calculation uses them. None of these affects
the unseen period's closes or VIX values.
