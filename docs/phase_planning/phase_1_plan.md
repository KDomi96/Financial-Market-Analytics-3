# Phase 1 plan: master data

Phase 1 produces two files. One is a clean daily dataset for 2018-2025 that
Phase 2 can use directly. The other is the same dataset for January-July 2026,
which stays untouched until the evaluation phases. Alongside them goes a record
of how both were built. The decisions behind the plan (Close prices, integer
calendar fields, VIX from Cboe) and their reasons are in
[methodology](../methodology.md#phase-1-master-data) and the
[source analysis](phase_1_analysis.md). This plan covers the order of work,
the files, and the checks.

## Inputs

| Data | Snapshot |
| --- | --- |
| Six stocks and S&P 500 | `data/raw/yahoo_finance/20261017T112037944190Z/` |
| VIX | `data/raw/cboe/20261024T163804809102Z/` |

Both snapshots are named in `configs/master_data.json`, so a rebuild never
picks up a newer download by accident. Before parsing the selected records,
the build checks that each manifest has `status: complete` and that each
selected file matches its recorded SHA-256. A historical-only run checks only
the historical Yahoo inputs. The shared Cboe history is hashed in full, then
restricted to the requested period before price validation and alignment.
The expected sizes are 2,011 historical and 145 unseen trading days.

## Master columns

| Group | Columns |
| --- | --- |
| Date | `Date` |
| Each stock | `<SYMBOL>_Open`, `_High`, `_Low`, `_Close`, `_AdjClose`, `_Volume`, `_Return` |
| S&P 500 | `GSPC_Close`, `GSPC_Return` |
| VIX | `VIX_Close` (Cboe's CLOSE) |
| Calendar | `Year`, `Quarter`, `Month` |

The symbols are MSFT, GOOGL, NVDA, AAPL, AMZN, and META. `AdjClose` is there
for reference only and is labelled as such in the data dictionary; later code
selects the columns it needs rather than taking every numeric column.
Dividends and split records stay in the interim files. S&P 500 volume is left
out because Yahoo's index volume is unreliable (it is zero on 2023-05-24), and
nothing needs the VIX open, high, or low.

## Steps

**1. Validate.** Each input file needs its required columns, unique and
increasing dates, and finite positive prices with consistent OHLC values.
Stock volume must be a positive whole number; index volume is not checked. A
failure stops the build. Nothing is filled, interpolated, deduplicated, or
dropped by an inner join to get past a problem. The pinned snapshots passed
all of these checks when I inspected them on 24 October 2026.

**2. Align.** The Yahoo S&P 500 dates define the trading calendar. Each
stock's dates must match it exactly. The Cboe VIX series is matched to the
same dates and must have a close on every one of them. Cboe also publishes
VIX on 32 days when stocks did not trade (27 historical, 5 unseen, including
2026-05-25). Those rows are excluded and written to the exclusion log. The
aligned data are saved as interim checkpoints, still including `Adj Close`,
`Dividends`, and `Stock Splits`.

**3. Calculate.** Daily returns are `100 * (Close_t / Close_{t-1} - 1)` for
the six stocks and the S&P 500, so 1.5 means 1.5%. The first historical return
(2018-01-02) has no earlier close and stays empty. The unseen build takes a
`prior_close` row from the aligned historical checkpoint for 2025-12-31,
to calculate its first return. The historical build never reads the unseen
files. `Year`, `Quarter`, and `Month` come from the date as integers.

**4. Flag large moves.** Every daily return above 15% in either direction is
listed in a large-moves table with a short note of its cause. On the
historical data this flags 14 rows, all of them known events, for example
META on 2022-02-03 (-26.4%) and the 2025-04-09 tariff-pause rally (NVDA
+18.7%, AAPL +15.3%). Flags never change the data. Unseen rows that exceed the
threshold are listed but not investigated.

**5. Save.** Write the two masters, the audit files, and a manifest.

## Files

| File | Contents |
| --- | --- |
| `configs/master_data.json` | Input snapshot IDs and output paths |
| `configs/phase1_large_move_notes.json` | Historical event notes and source URLs for flagged moves |
| `src/market_analytics/data/master.py` | Validation, alignment, calculations, and assembly |
| `scripts/build_master.py` | Thin command that runs the build |
| `notebooks/01_master_data.ipynb` | The same steps explained, with the checks and findings |
| `tests/test_master.py` | Small synthetic tests (below) |
| `docs/data_dictionary.md` | Every master column: meaning, unit, type, allowed missing values |
| `data/interim/aligned_historical.csv`, `aligned_unseen.csv` | Aligned source fields before calculations |
| `data/interim/excluded_rows.csv` | Date, period, instrument, and reason for every excluded row |
| `data/processed/master_historical.csv`, `master_unseen.csv` | The two masters |
| `data/processed/master_manifest.json` | Input snapshots and hashes, output hashes, settings, library versions |
| `outputs/metrics/phase1_quality_summary.csv` | Result of every check, with counts |
| `outputs/metrics/phase1_large_moves.csv` | Returns above 15% with their causes |
| `outputs/metrics/phase1_return_checks.csv` | Three independent Decimal calculations from raw Close strings |

The notebook explores first. The logic then moves into `master.py`, so that
the notebook and the command run the same code.

All CSVs are written with `\n` line endings. pandas would otherwise write
`\r\n` on Windows and `\n` in Docker, and the same data would get different
hashes. For the same reason `.gitattributes` gets `data/interim/** -text` and
`data/processed/** -text`, next to the existing rule for `data/raw/`.
The Phase 1 metric CSVs are also protected because their hashes are in the manifest.

## Checks

The tests use small made-up tables:

- A missing or duplicated date stops the build.
- Returns are in percent, and the first historical return is empty.
- The first unseen return uses the supplied prior close.
- The historical master is identical whether or not the unseen files exist.
- No value is ever filled in.

On the real data I will check the column schema, the 2,011 and 145 row
counts, VIX present on every date, and three returns worked out by hand,
including the step from 2025-12-31 to 2026-01-02. Running the build twice
must give identical output hashes.

The notebook must run from top to bottom with
`uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/01_master_data.ipynb`.
That needs `ipykernel` and `nbconvert` as development dependencies.

When the outputs exist, the data dictionary, the processing provenance in
`data_sources.md`, the build command in the README, and the new paths in the
directory guide get written or updated. The phase checklist then links to the
evidence.
