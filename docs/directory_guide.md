# Project directory guide

The project root is the existing `Final Project` folder. The approved directory
scaffold is present. Market-data acquisition, the Phase 1 master build, and the
Phase 2 exploratory analysis are implemented; later analytical components
remain planned.

## Root files

| File | Purpose | Current status |
| --- | --- | --- |
| `README.md` | Human entry point: scope, status, and eventually installation and end-to-end run instructions. | Created. |
| `.gitignore` | Excludes credentials, local environments, and caches from Git tracking. It does not filter submission ZIPs. | Created. |
| `.gitattributes` | Preserves data-file bytes across Git checkouts so manifest checksums remain valid. | Disables line-ending conversion under data/raw/, data/interim/, data/processed/, and for outputs/metrics/phase1_*.csv and outputs/metrics/eda/*.csv. |
| `.env.example` | Documents environment variable names with blank values. | Created with comments; provider-specific names are pending. |
| `pyproject.toml` | Defines the Python package, dependencies, supported Python versions, and selected tooling. | Includes yfinance, pandas, NumPy, matplotlib, and statsmodels; versions resolved in uv.lock. |
| `uv.lock` | Records the resolved dependency versions for uv. | Created. |
| `.python-version` | Selects the local Python patch version. | Python 3.12.13. |
| `Dockerfile` | Builds the Linux runtime from the locked project dependencies. | Default command runs the batch pipeline (master build, then EDA); Phase 1 and Phase 2 runs verified in Docker. |
| `.dockerignore` | Excludes local environments, tooling, credentials, and caches from the build context. | Created. |

The uv-managed `.venv/` environment is configured. Local uv tooling in `.tools/`
is ignored and is not part of the submission.

## Configuration and documentation

| Location | Purpose |
| --- | --- |
| `configs/` | Non-secret settings consumed by the pipeline. |
| `docs/` | Requirements and supporting documentation. |
| `docs/submission_requirements.md` | General submission obligations and final checklist. |
| `docs/methodology.md` | Analytical and engineering decisions, their status, and rationale. |
| `docs/data_sources.md` | Implemented acquisition provenance, coverage, caveats, and citations. |
| `docs/data_dictionary.md` | Every master and EDA table column, its unit and type, and allowed missing values or statuses. |
| `docs/phase_planning/` | Phase-specific implementation roadmaps for later reference; decisions and completion evidence remain in their existing documents. |
| `docs/phase_planning/phase_1_plan.md` | Phase 1 roadmap covering the master schema, cleaning, calculations, planned files, and verification. |
| `docs/phase_planning/phase_1_analysis.md` | Check of the Yahoo data against IBKR and Cboe, and why VIX comes from Cboe. |
| `docs/phase_planning/phase_2_plan.md` | EDA roadmap covering return/risk comparisons, all stock pairs, benchmark sensitivity, stability, VIX context, and verification. |
| `docs/phase_planning/phase_2_analysis.md` | EDA findings and limitations, with numbers traced to the saved tables and figures. |
| `docs/experiment_log.md` | Append-only record of each run's settings, date windows, and results, with links to saved outputs. Started with the Phase 2 EDA run. |
| `docs/deployment.md` | Future operational guide. |

## Data and the meaning of interim

`data/interim/` is a reproducible checkpoint after acquisition and before the
final datasets are assembled. It contains cleaned or aligned data that still
need further assembly or feature engineering. It is not an unstructured scratch
folder.

| Location | Purpose |
| --- | --- |
| `data/raw/` | Preserve source downloads unchanged so transformations can be audited. |
| `data/interim/` | Save useful intermediate cleaning and alignment results. |
| `data/processed/` | Store final datasets for analysis and modeling. |

Example data flow:

```text
data/raw/<source file>
    -> data/interim/<cleaned file>
    -> data/processed/<final dataset>
```

Save an interim file only when it is a useful inspection or restart point; not
every transformation needs one. All interim and processed files must be
regenerable from the documented inputs and code. Fitted preprocessing
parameters belong in `artifacts/`, while their transformed rows belong in the
data folders.

## Notebooks and source code

| Location | Purpose |
| --- | --- |
| `notebooks/` | Explain the analysis with code, plots, and narrative. The notebooks call reusable package functions. |
| `src/market_analytics/data/` | Download, read, validate, clean, align, and assemble source records. |
| `src/market_analytics/features/` | Derive features and model inputs. |
| `src/market_analytics/analysis/` | Calculate exploratory summaries. |
| `src/market_analytics/cointegration/` | Statistical relationship testing and ranking. |
| `src/market_analytics/trading/` | Strategy rules and backtest accounting. |
| `src/market_analytics/models/` | Fit, save, load, and evaluate models; provide forecasts. |
| `src/market_analytics/sentiment/` | Text processing and sentiment estimation. |
| `src/market_analytics/api/` | Provide routing, request validation, artifact loading, and inference responses. |
| `scripts/` | Thin command-line entry points that call the shared package. |
| `tests/` | Meaningful checks of data integrity, chronology, calculations, and API behavior. |
| `app/` | User-facing web interface that calls the API. |

The root package has an `__init__.py` so it can be installed and imported.
The data subpackage implements acquisition, source comparison, and the master
build; other functional subdirectories remain placeholders. Acquisition files are:

| Location | Purpose |
| --- | --- |
| `configs/yahoo_finance.json` | Eight Yahoo symbols and separate historical/unseen date boundaries. |
| `src/market_analytics/data/yahoo.py` | Downloads, source-preserving CSV exports, validation, and acquisition manifests. |
| `scripts/download_yahoo.py` | Thin executable entry point; see README for the verified command. |
| `tests/test_yahoo.py` | Offline checks for dates, missing data, and VIX nontrading records. |
| `data/raw/yahoo_finance/<UTC timestamp>/historical/` | Eight provider-returned CSVs for 2018-2025. |
| `data/raw/yahoo_finance/<UTC timestamp>/unseen/` | Eight provider-returned CSVs for January-July 2026. |
| `data/raw/yahoo_finance/<UTC timestamp>/manifest.json` | Settings, library versions, timestamps, hashes, validation, and calendar differences. |
| `configs/cboe.json`, `src/market_analytics/data/cboe.py`, `scripts/download_cboe.py` | Cboe VIX history download; the file is saved unchanged under `data/raw/cboe/<UTC timestamp>/`. |
| `configs/ibkr.json`, `src/market_analytics/data/ibkr.py`, `scripts/download_ibkr.py` | IBKR daily bars for the cross-check, saved under `data/raw/ibkr/<UTC timestamp>/{historical,unseen}/`; Git-ignored because IBKR data may not be redistributed. |
| `src/market_analytics/data/source_comparison.py`, `scripts/compare_sources.py` | Yahoo/IBKR/Cboe comparison; tables in `outputs/metrics/source_comparison/`. |

Raw CSVs preserve the records returned by yfinance, including missing values.
They are not byte-for-byte Yahoo HTTP responses.

Phase 1 files are:

| Location | Purpose |
| --- | --- |
| `configs/master_data.json` | Pinned input snapshots, formal periods, output paths, and return-check samples. |
| `configs/phase1_large_move_notes.json` | Historical event notes with source URLs; no unseen event investigation. |
| `src/market_analytics/data/master.py`, `scripts/build_master.py` | Reusable build and thin command-line entry point. |
| `notebooks/01_master_data.ipynb` | Executed explanation, historical findings, quality checks, and repeat-build checks. |
| `tests/test_master.py` | Small examples for date alignment, invalid inputs, return units, hashes, and historical isolation. |
| `data/interim/aligned_historical.csv`, `aligned_unseen.csv` | Aligned source fields, including corporate actions, before return/calendar calculations. |
| `data/interim/excluded_rows.csv` | Cboe-only observations inside the formal periods, with exclusion reasons. |
| `data/processed/master_historical.csv`, `master_unseen.csv` | Separate masters with the same 49-column schema including Date. |
| `data/processed/master_manifest.json` | Settings, versions, build/input hashes, and output hashes for the latest build. |
| `outputs/metrics/phase1_quality_summary.csv` | Each successful input and master-data check, with counts. |
| `outputs/metrics/phase1_large_moves.csv` | Returns exceeding 15%, with source notes for historical observations. |
| `outputs/metrics/phase1_return_checks.csv` | Independent calculations of three returns from raw Close strings. |
| `outputs/metrics/phase1_docker_validation.json` | Docker image/container identifiers, runtime versions, successful checks, and hashes matching Windows. |

Phase 2 files are:

| Location | Purpose |
| --- | --- |
| `configs/eda.json` | Historical input and manifest paths, stock order, adopted calculation settings, and output directories. |
| `src/market_analytics/analysis/eda.py`, `scripts/run_eda.py` | Input checks, summaries, pair correlations, benchmark regressions, rolling and VIX tables, metadata; thin entry point. |
| `src/market_analytics/analysis/eda_plots.py` | The nine EDA figures, drawn from the saved tables. |
| `scripts/run_pipeline.py` | Runs the master build and then the EDA; the Docker default command. |
| `notebooks/02_eda.ipynb` | Executed walk-through of the EDA tables and figures with short explanations. |
| `tests/test_eda.py` | Small examples for compounding, drawdowns, pairs, regressions, rolling windows, VIX groups, and historical isolation. |
| `outputs/metrics/eda/` | Ten EDA tables and `run_metadata.json` (input/settings hashes, VIX boundaries, versions, checks, table hashes). |
| `outputs/figures/eda/` | Nine PNG figures. |
| `outputs/metrics/phase2_docker_validation.json` | Docker run of the historical-only pipeline compared with the Windows results. |
| `outputs/metrics/phase2_review_validation.json` | Regression-test results, independent numerical checks, notebook execution, unchanged table hashes, and the Phase 2 leakage audit. |

## Fitted artifacts, generated results, and final reporting

| Location | Purpose |
| --- | --- |
| `artifacts/statistical/` | Fitted statistical parameters required for inference. |
| `artifacts/lstm/` | Trained networks and inference metadata. |
| `artifacts/preprocessing/` | Fitted transformations used consistently at inference time. |
| `outputs/metrics/` | Evaluation and comparison tables. |
| `outputs/backtests/` | Detailed trading results and summaries. |
| `outputs/predictions/` | Forecast records. |
| `outputs/figures/` | Exported visuals reused in the report or application. |
| `reports/` | Final audience-facing academic deliverables. |

Artifacts answer "what was fitted and what does inference need?" Outputs answer
"what did the analysis, forecasts, and evaluations produce?" Reports explain
the findings using those results.

## Placeholder files and packaging

Each initially empty leaf directory contains a `.gitkeep` marker so Git
preserves it. The marker has no runtime meaning and can be removed once the
folder contains real tracked files.

Final packaging will include relevant functional code, documentation, required
models/preprocessing, and evaluation outputs in one compressed folder. Include
permitted data or clear acquisition instructions as needed for reproducibility.
Exclude `.env`, secrets, virtual environments, caches, and irrelevant scratch
files explicitly. The working directory itself is not automatically the
submission archive.
