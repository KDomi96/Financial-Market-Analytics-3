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
VIX's zero volume as a measure of tradable activity. The extra VIX quote can
be cross-checked against Cboe during that phase. No cleaning has been applied.

An earlier snapshot has `status: failed` because its first validation policy
treated empty VIX holiday rows as missing trading observations. It is retained
locally for audit and is not included in the Git commit. Select the successful
snapshot above for subsequent processing.

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

## Sources and permitted use

- [yfinance documentation](https://ranaroussi.github.io/yfinance/): independent
  library accessing Yahoo Finance APIs; research/education and personal-use
  guidance, with links to Yahoo's applicable terms.
- [yfinance download reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html):
  date boundaries, adjustment flags, corporate actions, and missing-row settings.
- [Yahoo Finance S&P 500 history](https://finance.yahoo.com/quote/%5EGSPC/history/):
  benchmark identifier and provider price-field descriptions.
- [Cboe VIX historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data):
  original-source reference for a later cross-check; this snapshot was obtained
  from Yahoo, not Cboe.

Public display or redistribution through the eventual app requires checking
the applicable provider permissions. This acquisition does not establish
redistribution rights. Sentiment data have not been acquired; their source,
coverage, and role remain a separate decision.
