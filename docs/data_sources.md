# Market data sources and acquisition

The initial market dataset was acquired programmatically from Yahoo Finance
on 17 October 2026 using yfinance 1.7.0, pandas 3.0.6, and Python 3.12.13.
The exact installed dependencies are recorded in `uv.lock` and each acquisition
manifest. No API key is required by this downloader.

## Instruments and periods

| Instrument | Yahoo symbol | CSV filename in each period |
| --- | --- | --- |
| Microsoft | MSFT | MSFT.csv |
| Alphabet Class A | GOOGL | GOOGL.csv |
| NVIDIA | NVDA | NVDA.csv |
| Apple | AAPL | AAPL.csv |
| Amazon | AMZN | AMZN.csv |
| Meta Platforms | META | META.csv |
| S&P 500 price index | ^GSPC | GSPC.csv |
| Cboe VIX index | ^VIX | VIX.csv |

Alphabet Class A is used consistently rather than including both Alphabet
share classes. META is the current identifier used to retrieve its history.
The benchmark is the S&P 500 index, not an ETF proxy or total-return index.

Requests use daily observations. The historical request starts at 2018-01-01
and ends exclusively at 2026-01-01. The unseen request starts at 2026-01-01
and ends exclusively at 2026-08-01. Those boundaries include the project's
2018-2025 and January-July 2026 periods. Nontrading dates need not have records.
No fitting, pair selection, model tuning, or financial performance analysis
has been performed on either period during acquisition.

## Snapshot and verified coverage

The successful initial snapshot is:

`data/raw/yahoo_finance/20261017T112037944190Z/`

| Series | Historical rows | Unseen rows | Valid closing prices |
| --- | ---: | ---: | --- |
| Each of the six stocks | 2,011 | 145 | All rows |
| S&P 500 | 2,011 | 145 | All rows |
| VIX | 2,087 | 151 | 2,011 historical; 146 unseen |

Historical records span 2018-01-02 through 2025-12-31; unseen records span
2026-01-02 through 2026-07-31. The six stocks have identical date sets to the
downloaded S&P 500. VIX has a valid close on every S&P 500 date in both periods.
Date comparisons use this downloaded benchmark, not an independent exchange
calendar; agreement alone cannot detect a date missing from all series.

With `keepna=True`, Yahoo/yfinance returns 76 historical and five unseen VIX
rows with all price fields empty and zero volume. These dates are absent from
the stock benchmark calendar. It also returns a nonempty VIX observation for
2026-05-25, which has no corresponding S&P 500 row. The raw files preserve all
these records. The manifest lists the specific dates and missing-value counts.
Missing prices on actual benchmark dates remain validation errors.

Later cleaning should align to the documented stock trading calendar and
report excluded VIX-only rows. Do not fill closed-market stock prices or use
VIX's zero volume as a measure of tradable activity. Cboe's own file confirms
the 2026-05-25 value as a genuine holiday publication (see below). VIX for the
master comes from Cboe rather than this Yahoo file. No cleaning has been applied.

## Fields and preservation policy

Each CSV contains Open, High, Low, Close, Adj Close, Volume, Dividends, and
Stock Splits as returned by yfinance. Settings explicitly disable automatic
OHLC adjustment, back adjustment, repair, and rounding; corporate actions and
missing rows are retained. Records are serialized to CSV without cleaning,
date filtering, imputation, or feature calculation. These are library-returned
source records, not the original HTTP response bytes.

`auto_adjust=False` preserves both Close and Adj Close; it does not undo any
split adjustment Yahoo already applies to Close. Preserve both series and
corporate actions so the analytical adjustment policy can be chosen explicitly
before returns, cointegration, and P&L are calculated. The data are an acquisition-
time snapshot, not a guaranteed point-in-time historical archive. Later
downloads may revise earlier prices or adjustment factors.

Each dated folder contains separate historical and unseen subdirectories,
eight CSVs per subdirectory, and a manifest with request settings, acquisition
timestamps, instrument names, package versions, field lists, SHA-256 checksums,
date coverage, validation results, and calendar comparisons. Reruns create new
folders rather than overwrite source files. Commands are in `README.md`.
The root `.gitattributes` disables Git line-ending conversion under `data/raw/`
so committed source-file bytes continue to match their recorded checksums.

## Cboe VIX history (used for VIX)

VIX in the master comes from Cboe's official daily history file, not from
Yahoo. The reasons are in the [Phase 1 source analysis](phase_planning/phase_1_analysis.md).

Snapshot: `data/raw/cboe/20261024T163804809102Z/VIX.csv`, downloaded on
24 October 2026 with `scripts/download_cboe.py` from
`https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`
(Cboe redirects to `cdn-api.cboe.com`). The response body is saved unchanged,
so unlike the Yahoo files this is the provider's original file. It holds
9,301 daily rows from 1990-01-02 to 2026-10-23 with columns DATE, OPEN, HIGH,
LOW, and CLOSE; 2,038 rows fall in the historical period and 150 in the unseen
period. The manifest records the URL, SHA-256 checksum, and row counts.

Since 30 May 2022 Cboe has published VIX on US stock-market holidays: 27 such
days in the historical period and 5 in the unseen period, including
2026-05-25. Stocks did not trade on those dates, so they are excluded when VIX
is aligned to the stock calendar.

## Interactive Brokers (cross-check only)

Snapshot: `data/raw/ibkr/20261024T163751761776Z/`, downloaded on 24 October
2026 with `scripts/download_ibkr.py` through a read-only IB Gateway session
(ib_async 2.1.0, API server version 178). It contains daily `TRADES` bars for
the same eight instruments: date, open, high, low, close, volume, average
(VWAP), and barCount. IBKR documents `TRADES` bars as split-adjusted but not
dividend-adjusted, and its volume as filtered. The S&P 500 is IBKR contract
`SPX` and VIX is `VIX`, both on CBOE.

IBKR requests take an end time and a duration, not a start date. The windows
used ("9 Y" ending 2026-01-01 and "150 D" ending 2026-08-01) are wider than the
formal periods, and the extra rows are kept as returned; each period has
exactly 2,011 and 145 rows inside its formal dates. The manifest records the
requests, contract IDs, checksums, and per-period row counts, and nothing
about the account. Re-running the download needs an IBKR account with US
equity and Cboe index market data. These data are not used to build the master.

**The IBKR price files are not published with this project.** IBKR's Market
Data and Analytics Subscriber Agreement says the data remain the property of
IBKR and its data suppliers, and clause 3 (headed "No Right to Redistribute")
adds: "Subscriber agrees not to reproduce, distribute, sell or commercially
exploit the Software or Data in any manner without the written consent of IB
and/or the Data Supplier." I did not ask for consent, so nothing from IBKR is
committed: `data/raw/ibkr/` is excluded by `.gitignore`, manifests included,
and the comparison tables and notes contain no per-day IBKR prices, only
summary statistics, counts, dates, and yes/no flags. I read the agreement as published on
IBKR's website; I could not retrieve the separate Market Data API
Acknowledgement signed in the client portal, and exchange-level terms may add
further limits. Anyone wanting to reproduce the cross-check needs their own
IBKR account and data subscriptions and can regenerate the snapshot with
`scripts/download_ibkr.py`. The comparison tables in
`outputs/metrics/source_comparison/` and the conclusions in the
[Phase 1 source analysis](phase_planning/phase_1_analysis.md) are my own
results.

## Sources and permitted use

- [yfinance documentation](https://ranaroussi.github.io/yfinance/): independent
  library accessing Yahoo Finance APIs; research/education and personal-use
  guidance, with links to Yahoo's applicable terms.
- [yfinance download reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html):
  date boundaries, adjustment flags, corporate actions, and missing-row settings.
- [Yahoo Finance S&P 500 history](https://finance.yahoo.com/quote/%5EGSPC/history/):
  benchmark identifier and provider price-field descriptions.
- [Cboe VIX historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data):
  the official VIX history, downloaded on 24 October 2026 and used for VIX in
  the master.
- [IBKR TWS API historical data documentation](https://interactivebrokers.github.io/tws-api/historical_bars.html):
  bar fields, `TRADES` adjustment, and volume filtering for the cross-check
  snapshot.
- [IBKR Market Data and Analytics Subscriber Agreement](https://ndcdyn.interactivebrokers.com/Universal/servlet/Registration_v2.formSampleView?file=IBISAgreement.html):
  the redistribution restriction that keeps the IBKR price files out of the
  public repository.

Public display or redistribution through the eventual app requires checking
the applicable provider permissions. This acquisition does not establish
redistribution rights. Sentiment data have not been acquired; their source,
coverage, and role remain a separate decision.
