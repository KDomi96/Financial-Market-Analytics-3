# Project directory guide

The project root is the existing `Final Project` folder. The approved directory
scaffold is present. Market-data acquisition, the Phase 1 master build, and the
Phase 2 exploratory analysis, Phase 3 pair selection, Phase 4 statistical
baseline, and Phase 5 LSTM comparison are implemented. Sentiment, the API,
and the web interface remain planned.

## Root files

| File | Purpose | Current status |
| --- | --- | --- |
| `README.md` | Human entry point: scope, status, and eventually installation and end-to-end run instructions. | Created. |
| `.gitignore` | Excludes credentials, local environments, and caches from Git tracking. It does not filter submission ZIPs. | Created. |
| `.gitattributes` | Preserves data-file bytes across Git checkouts so manifest checksums remain valid. | Covers raw/interim/processed data, phase metric CSVs, and statistical artifacts. |
| `.env.example` | Documents environment variable names with blank values. | Created with comments; provider-specific names are pending. |
| `pyproject.toml` | Defines the Python package, dependencies, supported Python versions, and selected tooling. | Includes yfinance, pandas, NumPy, matplotlib, statsmodels, and CPU-only torch; versions resolved in uv.lock. |
| `uv.lock` | Records the resolved dependency versions for uv. | Created. |
| `.python-version` | Selects the local Python patch version. | Python 3.12.13. |
| `Dockerfile` | Builds the Linux runtime from the locked project dependencies. | Default command runs Phases 1-5; both modes execute successfully. Independent LSTM retraining differs numerically across Windows/Linux; saved-weight inference is verified. |
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
| `docs/data_dictionary.md` | Master, EDA, and pair-selection columns, units, types, and allowed missing values or statuses. |
| `docs/phase_planning/` | Phase-specific implementation roadmaps for later reference; decisions and completion evidence remain in their existing documents. |
| `docs/phase_planning/phase_1_plan.md` | Phase 1 roadmap covering the master schema, cleaning, calculations, planned files, and verification. |
| `docs/phase_planning/phase_1_analysis.md` | Check of the Yahoo data against IBKR and Cboe, and why VIX comes from Cboe. |
| `docs/phase_planning/phase_2_plan.md` | EDA roadmap covering return/risk comparisons, all stock pairs, benchmark sensitivity, stability, VIX context, and verification. |
| `docs/phase_planning/phase_2_analysis.md` | EDA findings and limitations, with numbers traced to the saved tables and figures. |
| `docs/phase_planning/phase_3_plan.md` | Pair-selection roadmap covering all 30 OLS directions, 15 Johansen tests, ranking, fitted spreads, shortlist, and verification. |
| `docs/phase_planning/phase_3_analysis.md` | Pair-selection findings, exploratory shortlist, diagnostics, and limitations traced to saved outputs. |
| `docs/phase_planning/phase_4_plan.md` | Statistical-baseline roadmap: fixed normalization, signal rules, stock-leg accounting, output files, and verification. |
| `docs/phase_planning/phase_4_analysis.md` | Historical/unseen findings, signal and trade counts, stock-leg P&L, exposures, and limitations traced to saved outputs. |
| `docs/phase_planning/phase_5_plan.md` | LSTM roadmap: earlier-fit validation, dated features/sequences, model selection, final refit, forecast-filtered comparison, artifacts, and checks. |
| `docs/phase_planning/phase_5_analysis.md` | Forecast and trading findings, seed sensitivity, fitted scales, and the Windows/Linux retraining limitation. |
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
build. Analysis, cointegration, trading, features, and models implement
Phases 2-5; sentiment and serving subdirectories remain placeholders.
Acquisition files are:

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
| `scripts/run_pipeline.py` | Runs Phases 1-4 in order; the Docker default command. |
| `notebooks/02_eda.ipynb` | Executed walk-through of the EDA tables and figures with short explanations. |
| `tests/test_eda.py` | Small examples for compounding, drawdowns, pairs, regressions, rolling windows, VIX groups, and historical isolation. |
| `outputs/metrics/eda/` | Ten EDA tables and `run_metadata.json` (input/settings hashes, VIX boundaries, versions, checks, table hashes). |
| `outputs/figures/eda/` | Nine PNG figures. |
| `outputs/metrics/phase2_docker_validation.json` | Docker run of the historical-only pipeline compared with the Windows results. |
| `outputs/metrics/phase2_review_validation.json` | Regression-test results, independent numerical checks, notebook execution, unchanged table hashes, and the Phase 2 leakage audit. |

## Fitted artifacts, generated results, and final reporting

Phase 3 files are:

| Location | Purpose |
| --- | --- |
| `configs/pair_selection.json` | Adopted historical input, statistical settings, ranking rule, and output paths. |
| `src/market_analytics/cointegration/selection.py`, `scripts/run_pair_selection.py` | Input validation, tests, pair-level correction, ranking, diagnostics, fitted-parameter export, and thin entry point. |
| `src/market_analytics/cointegration/plots.py` | Four figure groups covering all 15 pairs. |
| `notebooks/03_pair_selection.ipynb` | Executed historical analysis using the shared package, with output-hash and artifact checks. |
| `tests/test_pair_selection.py` | Direction, pair correction, agreement ranking, lag/rank logic, numerical failure, and historical isolation checks. |
| `outputs/metrics/pair_selection/` | Eight tables and run metadata, including all directional tests, all Johansen results, and the justified shortlist. |
| `data/processed/pair_spreads_historical.csv` | Unnormalized, explicitly oriented residuals for all 15 pairs. |
| `artifacts/statistical/phase3_v1/<PAIR_ID>/` | Selected-direction full-history OLS coefficients and reconstruction metadata. |
| `outputs/figures/pair_selection/` | Fitted prices, residual histories, evidence comparison, and subperiod hedge ratios. |
| `outputs/metrics/phase3_docker_validation.json` | Historical-only Docker reproduction, numeric differences, and matching discrete decisions. |
| `outputs/metrics/phase3_review_validation.json` | Tests, notebook execution, repeat hashes, independent calculations, and the leakage audit. |

| Location | Purpose |
| --- | --- |
| `configs/statistical_baseline.json` | Adopted Phase 4 rules, periods, capital/costs, and output locations. |
| `src/market_analytics/trading/`, `scripts/run_statistical_baseline.py` | Normalization, signals, next-open stock-leg accounting, plots, and thin entry point. |
| `notebooks/04_statistical_baseline.ipynb`, `tests/test_statistical_baseline.py` | Executed walk-through and known-input normalization, timing, accounting, boundary, and preservation checks. |
| `data/processed/statistical_baseline/` | Historical and unseen residual/Z-score datasets. |
| `artifacts/statistical/phase4_v1/<PAIR_ID>/` | Fixed 2025 normalization, direction, lineage, and fit metadata. |
| `outputs/backtests/statistical_baseline/phase4_v1/` | Separate historical/unseen signals, executions, trades, and daily accounts. |
| `outputs/metrics/statistical_baseline/phase4_v1/` | Summaries, diagnostics, reversion events, metadata, and evaluation contract. |
| `outputs/figures/statistical_baseline/phase4_v1/` | Z-score, equity, and drawdown figures for each period. |
| `outputs/metrics/phase4_review_validation.json`, `phase4_docker_validation.json` | Independent checks, notebook/test results, leakage audit, and Docker comparison. |
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

Phase 5 is implemented, with saved results and an executed notebook. The
reported run is `phase5_v2`. It repeats the `phase5_v1` settings after review
fixes to diagnostics, figures, and summary counts; the v1 files are kept as the
earlier evaluated record and are not cited by the findings. The
[Phase 5 plan](phase_planning/phase_5_plan.md#files) gives the planned file map.
Its main additions are:

| Location | Purpose |
| --- | --- |
| `configs/lstm_forecast.json`, `notebooks/05_lstm_comparison.ipynb` | Experiment settings and the phase's executable explanation. |
| `src/market_analytics/features/sequences.py` | Earlier-fit spread parameters, trailing features, scaling, dated windows, and exclusion records. |
| `src/market_analytics/models/{lstm,forecasting,plots}.py` | Network/training/inference, stage orchestration and metrics, and figures. |
| `src/market_analytics/trading/forecast_filter.py` | Dated signal adapter and day-five entry filter using the existing accounting engine. |
| `src/market_analytics/pipeline.py` | Ordered-pipeline helper that reuses the Phase 3 handoff once Phase 4 has frozen it. |
| `scripts/run_lstm_forecast.py` | Offline selection, refit, evaluation, and historical-only entry point. |
| `data/processed/lstm/phase5_v2/` | Selection/final features, sample date index, and excluded samples. |
| `artifacts/statistical/phase5_v2/selection/` | Earlier OLS and 2023 normalization for conditional validation. |
| `artifacts/preprocessing/phase5_v2/`, `artifacts/lstm/phase5_v2/` | Fitted input scaling, trial/final weights, metadata, and reload examples. |
| `outputs/predictions/lstm/phase5_v2/`, `outputs/metrics/lstm/phase5_v2/` | Dated forecasts, experiments, errors, direction base rates, filter decisions, comparisons, and run contracts. |
| `outputs/backtests/lstm_comparison/phase5_v2/`, `outputs/figures/lstm/phase5_v2/` | Matched baseline/filtered ledgers and the phase's figures. |
| Matching `phase5_v1/` folders | The first evaluated run, retained unchanged. |
| `tests/test_lstm_sequences.py`, `tests/test_lstm_forecast.py`, `tests/test_forecast_filter.py`, `tests/test_pipeline_freeze.py` | Chronology, artifact reload, selection, forecast metrics, filter decisions, accounting, and pipeline handoff checks. |
| `docs/phase_planning/phase_5_analysis.md` | Findings from the saved evaluations and their limits. |
| `outputs/metrics/phase5_review_validation.json`, `phase5_docker_validation.json` | Independent calculations, test results, repeated hashes, isolation checks, and Docker runs. |

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
