# Project directory guide

The project root is the existing `Final Project` folder. The approved directory
scaffold is present. Market-data acquisition is implemented; later analytical
components remain planned. Implemented acquisition files are listed below.

## Root files

| File | Purpose | Current status |
| --- | --- | --- |
| `README.md` | Human entry point: scope, status, and eventually installation and end-to-end run instructions. | Created. |
| `.gitignore` | Excludes credentials, local environments, and caches from Git tracking. It does not filter submission ZIPs. | Created. |
| `.gitattributes` | Preserves raw source-file bytes across Git checkouts so manifest checksums remain valid. | Disables line-ending conversion under data/raw/. |
| `.env.example` | Documents environment variable names with blank values. | Created with comments; provider-specific names are pending. |
| `pyproject.toml` | Defines the Python package, dependencies, supported Python versions, and selected tooling. | Includes yfinance and pandas; versions resolved in uv.lock. |
| `uv.lock` | Records the resolved dependency versions for uv. | Created. |
| `.python-version` | Selects the local Python patch version. | Python 3.12.13. |
| `Dockerfile` | Builds the Linux runtime from the locked project dependencies. | Created; default command checks the package import. |
| `.dockerignore` | Excludes local environments, tooling, credentials, and caches from the build context. | Created. |

The uv-managed `.venv/` environment is configured. Local uv tooling in `.tools/`
is ignored and is not part of the submission.

## Configuration and documentation

| Location | Purpose |
| --- | --- |
| `configs/` | Non-secret settings consumed by the pipeline. |
| `docs/` | Requirements and supporting documentation. |
| `docs/submission_requirements.md` | General submission obligations and final checklist. |
| `docs/methodology.md` | Future record of analytical decisions and their rationale. |
| `docs/data_sources.md` | Implemented acquisition provenance, coverage, caveats, and citations. |
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
The data subpackage implements Yahoo acquisition; other functional subdirectories
remain placeholders. Current acquisition files are:

| Location | Purpose |
| --- | --- |
| `configs/yahoo_finance.json` | Eight Yahoo symbols and separate historical/unseen date boundaries. |
| `src/market_analytics/data/yahoo.py` | Downloads, source-preserving CSV exports, validation, and acquisition manifests. |
| `scripts/download_yahoo.py` | Thin executable entry point; see README for the verified command. |
| `tests/test_yahoo.py` | Offline checks for dates, missing data, and VIX nontrading records. |
| `data/raw/yahoo_finance/<UTC timestamp>/historical/` | Eight provider-returned CSVs for 2018-2025. |
| `data/raw/yahoo_finance/<UTC timestamp>/unseen/` | Eight provider-returned CSVs for January-July 2026. |
| `data/raw/yahoo_finance/<UTC timestamp>/manifest.json` | Settings, library versions, timestamps, hashes, validation, and calendar differences. |

Raw CSVs preserve the records returned by yfinance, including missing values.
They are not byte-for-byte Yahoo HTTP responses. No interim or processed market
datasets have been created yet.

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
