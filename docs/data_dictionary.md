# Master data dictionary

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
