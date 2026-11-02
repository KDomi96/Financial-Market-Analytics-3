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
master comes from Cboe rather than this Yahoo file. Raw files remain uncleaned;
the derived files are described under processing provenance below.

## Fields and preservation policy

Each CSV contains Open, High, Low, Close, Adj Close, Volume, Dividends, and
Stock Splits as returned by yfinance. Settings explicitly disable automatic
OHLC adjustment, back adjustment, repair, and rounding; corporate actions and
missing rows are retained. Records are serialized to CSV without cleaning,
date filtering, imputation, or feature calculation. These are library-returned
source records, not the original HTTP response bytes.

`auto_adjust=False` preserves both Close and Adj Close; it does not undo any
split adjustment Yahoo already applies to Close. Preserve both series and
corporate actions. The adopted Close policy is recorded in methodology before
returns, cointegration, and P&L calculations. The data are an acquisition-
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

## Phase 1 processing provenance

The master build on 25 October 2026 uses the Yahoo snapshot
`20261017T112037944190Z` for the six stocks and S&P 500, and the Cboe snapshot
`20261024T163804809102Z` for VIX. No IBKR records enter the build. Raw files
remain unchanged. Snapshot IDs, selected input hashes, build-file hashes,
settings, and Python/pandas versions are recorded in
`data/processed/master_manifest.json`.

The aligned checkpoints retain the source price fields and corporate actions.
Each stock must match the S&P 500 dates exactly; Cboe must provide VIX on every
date. The 27 historical and five unseen Cboe-only dates are listed in
`data/interim/excluded_rows.csv`. Rows outside each formal period are outside
the build's scope. No prices are filled, interpolated, clipped, or patched.

The historical master contains 2,011 dates from 2018-01-02 to 2025-12-31, and
the unseen master contains 145 dates from 2026-01-02 to 2026-07-31. Both have
49 columns including Date. The historical file has seven missing values:
the first stock and benchmark returns. The first unseen returns use the
last historical close and are present. Returns use Close; AdjClose is retained
for reference. The field definitions are in [the data dictionary](data_dictionary.md).

The build saves 64 passing quality checks in
`outputs/metrics/phase1_quality_summary.csv`. Three independently calculated
returns, including a split date and the first unseen date, are saved in
`outputs/metrics/phase1_return_checks.csv`. Their largest absolute difference
from the build is below 0.0000000001 percentage points. Repeat builds reproduce
all eight generated CSV hashes and the manifest bytes in the local environment.
The executed `notebooks/01_master_data.ipynb` records these checks and findings.

The Docker build was also verified on 25 October 2026. It starts without
prebuilt interim/processed files and regenerates all eight CSVs from the
permitted raw snapshots. Their hashes match Windows exactly; all 64 data
checks and 13 offline tests pass. The container runs as UID 10001 and exits
with code 0. `outputs/metrics/phase1_docker_validation.json` records the image,
container, versions, and matching hashes. The manifest itself is byte-identical
on Windows and in Docker, including the hash of the build module.

The historical large-move table contains 14 stock observations with absolute
daily returns above 15%. They are retained, with event notes and source URLs
from `configs/phase1_large_move_notes.json`; earnings releases and Federal
Reserve announcements provide the event context, and Reuters provides the
DeepSeek and tariff-pause reporting. The notes do not establish that any event
was the sole cause of a move. Unseen flags are saved without event investigation.
The source limitations in the Phase 1 source analysis still apply.

## Sentiment benchmark snapshots

The first benchmark snapshot is
`data/raw/sentiment/benchmarks/20261102T173344495719Z/`. It was downloaded on
2 November 2026 using `scripts/download_sentiment_benchmarks.py` in the locked
venv. No dependencies were added. Its manifest records URLs, source revisions,
download times, file sizes, SHA-256 hashes, source summaries, and acquisition
settings/code hashes. All seven saved file hashes and dataset counts were
checked independently after the download. Source records are unchanged.

| Dataset | Downloaded source | Observed contents |
| --- | --- | --- |
| FiQA 2018 Task 1 headlines | `dayanfcosta/fiqa-2018-task1`, revision `acd0f4cfafa6421774bc8f009e8fa3e0ec441357` | Training file: 438 headline records, 503 target annotations with numeric scores, 378 records with one annotation. Test file: 93 headlines without gold scores. |
| FinEntity | Authors' `yixuantt/FinEntity`, revision `3b6cedc5485b669c2ed168f1d949f517636eb7b8` | 979 paragraphs and 2,131 annotations: 503 positive, 498 negative, and 1,130 neutral. There are 390 paragraphs with one annotation before preparation. |

### FiQA source and limitations

The [organizer page](https://sites.google.com/view/fiqa/home) describes
target-specific sentiment scores from -1 to +1 and links its training and
test downloads. Both linked Google Drive files returned errors during source
discovery. The local files therefore come from a pinned
[challenge-participant repository](https://github.com/dayanfcosta/fiqa-2018-task1),
whose README identifies its FiQA submission. The organizer page and the mirror's
README are saved alongside the data. The mirror was not verified byte for byte
against the unavailable organizer release.

The training file has 438 headline records and 503 target scores, ranging from
-0.938 to 0.975. These are the downloaded counts, which differ from the 436
training headlines reported in the [challenge paper](https://andrefreitas.org/papers/www_fiqa_2018.pdf).
The 93 test headlines have targets and snippets but no sentiment scores.
They cannot provide test accuracy. The labeled training file is available for
external evaluation of the unchanged checkpoint; it is not used to fit it.
Microblog files were not downloaded because the planned study uses headlines.

The organizer page states non-commercial use for its training and testing
downloads. The mirror provides no separate dataset licence. The original
scores, targets, snippets, and aspect fields are preserved; no class labels
have been derived yet.

### FinEntity source and limitations

The [authors' repository](https://github.com/yixuantt/FinEntity) supplies
`data/FinEntity.json` and links the
[authors' Hugging Face dataset](https://huggingface.co/datasets/yixuantt/FinEntity).
Its saved dataset card, revision `e86e5451a1fce4731fe07c710649a229d92e5cab`,
declares the `odc-by` licence. The [paper](https://arxiv.org/html/2310.12406)
describes the Reuters source, annotation procedure, and three sentiment classes.

The download check found 11 repeated paragraph texts in the full source.
For 70 annotations, `content[start:end]` differs from the saved entity value
using an end-exclusive substring check. Label names agree across the `tag`
and `label` fields, and all offsets are within the corresponding paragraph.
These are source issues, not repairs made during acquisition. The planned
evaluation excludes inconsistent spans and duplicate texts, then records the
retained single-annotation count. A whole-paragraph classifier does not solve
the full entity recognition and multi-entity sentiment task.

Raw sentiment snapshots are excluded from Git. Their presence locally does
not establish permission to redistribute the underlying news text. The first
benchmark downloads alone do not establish 2026 news coverage. Subsequent
model, screen-file, and pilot acquisition is recorded below.

## Google News RSS preliminary requests

Three requests to `https://news.google.com/rss/search` returned HTTP 200 on
2 November 2026 from the project venv, using Python's standard library.
Each used `hl=en-US`, `gl=US`, and `ceid=US:en`, without an API key or sign-in.

| Search query (`q`) | Raw item count | Earliest / latest reported publication time (UTC) |
| --- | --- | --- |
| `Microsoft (stock OR shares OR earnings) after:2026-01-01 before:2026-01-08` | 24 | 2026-01-02 08:00 / 2026-01-08 08:00 |
| `NVIDIA (stock OR shares OR earnings) after:2026-07-01 before:2026-07-08` | 10 | 2026-07-02 07:00 / 2026-07-08 07:00 |
| `Microsoft stock when:7d` | 100 | 2026-10-26 17:06:07 / 2026-11-02 17:31:02 |

These were connectivity and retrieval probes. The responses were inspected
in memory rather than saved as source snapshots, and the counts precede
relevance, date-boundary, and duplicate checks. The queries are recorded here
to explain the next collection step, not as the final six-company query set.
In particular, the historical results included the dates named by `before:`;
the collector must check returned dates rather than assume boundary semantics.

The older responses used repeated fixed publication times. That observation
does not establish their actual publication times or historical availability.
The saved pilot must examine timestamp precision before session assignment;
uncertain times support publication-date summaries only. The recent query's
100 items also show why short windows and possible-limit flags are needed.

The [GNews documentation](https://github.com/ranahaani/GNews#results-specification)
describes its Google News RSS backend, language/region and date settings, and
default 100-result setting. The planned collector accesses RSS directly.
The saved pilot and full collection are recorded below.
Retrieved headlines form a sample of indexed coverage, not a complete archive.

## Sentiment model, overlap screen, and saved pilot

The second benchmark snapshot is
`data/raw/sentiment/benchmarks/20261102T194353691191Z/`. It adds the unchanged
Financial PhraseBank v1.0 zip and dataset card at revision
`8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964`. The zip is read directly; no remote
dataset loader is executed. Its 50%-agreement file has 4,846 sentences and is
used only for the overlap screen. The saved card declares CC BY-NC-SA 3.0.
The nine files match their manifest hashes. FiQA and FinEntity's pinned source
files match the first snapshot; the live FiQA organizer page changed.

FinBERT's six planned files are saved under
`artifacts/sentiment/sentiment_v1/finbert/` at revision
`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`. The
[model record](../artifacts/sentiment/sentiment_v1/model_revision.json) gives
the canonical URLs, download times, sizes, hashes, and licence. The saved
model card declares CC BY-NC-SA 4.0, copyright MIH AI B.V. The 437,965,908-byte
safetensors file's SHA-256 also matches the pinned repository's LFS metadata.
The other framework weight files were not downloaded. Model loading uses
local files only; the three labels come from the saved configuration.

The unscored Google News pilot is saved under
`data/raw/sentiment/google_news/20261102T195054616236Z/`. It covers the first
full Monday-Friday week of each month, January-July 2026, for all six
companies. The manifest records 68 attempts for 42 initial windows, including
split requests. Its 55 leaf windows comprise 54 successful requests and one
capped single-day request. Raw responses, request URLs, intended windows,
attempts, collection times, and hashes remain local.

The first cleaning retained 1,016 headlines, the count on which the pilot
decision was made; see the
[first pilot report](../outputs/metrics/sentiment/sentiment_v1/pilot_report.json).
The corrected cleaning also reads the responses of split windows. It retains
1,287 headlines and logs 1,916 exclusions: 781 outside the intended window,
720 duplicate GUIDs, 247 without the queried company in the title, 112 naming
several of the six companies, and 56 duplicate titles. Of the retained items,
1,284 have the date-only Pacific-midnight pattern and three have other times.
This heuristic does not establish historical availability. The
[corrected pilot report](../outputs/metrics/sentiment/sentiment_v2/pilot_report.json)
and accompanying coverage, publisher, title-format, and timestamp tables give
the counts. All six companies passed the adopted coverage rule under both
counts, with the same usable weeks, and the queries were kept unchanged.

## Full Google News snapshot

The full Google News snapshot is
`data/raw/sentiment/google_news/20261102T195614519732Z/`, collected on
2 November 2026 for 1 January-31 July 2026. Its 326 attempts cover 186 initial
Saturday-Friday company windows. After splitting, 251 leaf windows succeeded
and five single-day windows remained capped; none failed. All saved response
hashes were independently checked. The 70 split windows' own responses are
part of the snapshot. In 42 of them, the final narrower requests together
returned fewer than the 100 items of the wider request, so cleaning reads
both. The corrected cleaning retains 5,715 headlines, of which 5,704 fit the
Pacific-midnight date-only rule and 11 have other times. The first cleaning,
which skipped the split windows' responses, retained 3,846.
The manifest preserves each request, raw response, reported time, and
collection time. This retrospective snapshot does not prove historical
availability or completeness. Counts and exclusions are in
[the findings](phase_planning/sentiment_analysis.md#retrieved-news-coverage).

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
the applicable provider permissions. Acquisition does not establish
redistribution rights. The sentiment benchmarks, model, pilot, and full
six-company snapshot have been acquired. Their source and role are recorded
in methodology; saved manifests and coverage tables document what was retrieved.
