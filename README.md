# Financial Market Analytics

A postgraduate technology-stock analytics project.

## Current status

Phase 1 produces validated historical and unseen master datasets from the
pinned Yahoo and Cboe snapshots. Phase 2 describes the historical master:
return and risk, all 15 stock pairs, S&P 500 sensitivity, stability over time,
and VIX context. Phase 3 compares all pairs, saves their fitted spreads, and
carries AMZN_META and NVDA_AMZN forward as exploratory candidates. No pair
meets all the adopted support conditions. Phase 4 applies fixed 2025
normalization and saves baseline signals, stock-leg fills, trades, and daily
accounts. Phase 5 saves the fitted LSTMs, dated forecasts, persistence errors,
and matched strategy comparisons. The separate sentiment study evaluates
FinBERT on FiQA and FinEntity and describes 5,715 collected Google News
headlines, with saved-input local and Docker reproduction. API and web
interface work remain.
The Python 3.12.13 environment is managed with uv. Docker configuration is
provided for the environment.

The sentiment dependencies changed `uv.lock` after the evaluated Phase 5 run.
Its saved contract still requires the earlier lock. Keep the existing
Phase 1-5 outputs and run sentiment separately; the current full pipeline
will refuse to reuse Phase 5 with the new lock. Reproducing the earlier run
requires its original checkout and lock, not changing the saved contract.
The numbered-phase commands below document those earlier runs; use their
matching checkout when reproducing the evaluated outputs.

## Environment setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (the initial
setup uses uv 0.13.1), then run from the project root:

```powershell
uv sync --locked
uv run --locked python -c "import market_analytics; print('Package import OK')"
```

uv creates `.venv/` and installs the local package. `.python-version` selects
Python 3.12.13. Project dependencies belong in `pyproject.toml`; `uv.lock` records
the resolved versions. Both files belong in version control, while `.venv/`
does not. Runtime dependencies currently include yfinance, pandas, NumPy,
matplotlib, statsmodels, torch, transformers, vaderSentiment, and scikit-learn.

On this workstation, uv is available as the project-local `.tools/uv.exe`.
Use `.\.tools\uv.exe` in place of `uv` in the commands above if uv is not on PATH.
The tool directory is ignored by Git and Docker and is not a submission file.
If the default user cache is unavailable in a restricted environment, use
`uv --cache-dir .tools/uv-cache` in place of `uv`.

Use `uv add PACKAGE` to add a runtime dependency or `uv add --dev PACKAGE` for a
development tool. These commands update both dependency files. Use `uv run` for
project commands so they execute inside the project environment. PowerShell
activation is optional: `.\.venv\Scripts\Activate.ps1`.

## Download Yahoo Finance data

Run from the project root, with network access:

```powershell
uv run --locked python scripts/download_yahoo.py
```

On this workstation, the verified command is:

```powershell
.\.tools\uv.exe --cache-dir .tools/uv-cache run --locked python scripts/download_yahoo.py
```

`configs/yahoo_finance.json` contains the eight instrument identifiers and the
two required periods. Each run creates a new dated folder under
`data/raw/yahoo_finance/`, with separate `historical/` and `unseen/` CSVs and a
`manifest.json`. The manifest records provenance, settings, versions, hashes,
coverage, missing values, and calendar differences. Use snapshots whose manifest
has `status: complete`. Reruns preserve earlier snapshots; provider revisions
can change later downloads.

The acquisition and master-build checks have a small offline test suite:

```powershell
uv run --locked python -m unittest discover -s tests -v
```

## Download Cboe VIX and the IBKR cross-check

VIX for the master comes from Cboe's official history file:

```powershell
uv run --locked python scripts/download_cboe.py
```

The IBKR download is only a cross-check. It needs IB Gateway (or TWS) running
and logged in, with the API enabled and set to read-only on port 4001, and
market data for US stocks and Cboe indices. `ib_async` is supplied for the run
rather than added to the project, because it pins an older `tzdata`. No IBKR data
is included in the repository because IBKR's subscriber agreement forbids
redistributing its data (details in
[data sources](docs/data_sources.md)), so this step only works with your own
IBKR account:

```powershell
uv run --locked --with ib_async==2.1.0 python scripts/download_ibkr.py
```

To compare the three sources and write the tables to
`outputs/metrics/source_comparison/`:

```powershell
uv run --locked python scripts/compare_sources.py --yahoo data/raw/yahoo_finance/20261017T112037944190Z --ibkr data/raw/ibkr/20261024T163751761776Z --cboe data/raw/cboe/20261024T163804809102Z
```

All three commands were run on this workstation with `.\.tools\uv.exe
--cache-dir .tools/uv-cache` in place of `uv`. The results and the reasons for
the chosen sources are in the [Phase 1 source analysis](docs/phase_planning/phase_1_analysis.md).

See [data sources and acquisition results](docs/data_sources.md), including
VIX holiday records handled during master-data alignment. Downloading
data does not fit models or use the unseen period for analytical decisions.

## Download sentiment benchmarks

The Sentiment Phase evaluates the unchanged sentiment model separately on
FiQA headlines and FinEntity paragraphs. Financial PhraseBank is downloaded
only for the overlap screen. Download the pinned source files with:

```powershell
uv run --locked python scripts/download_sentiment_benchmarks.py
```

On this workstation, use `.\.tools\uv.exe --cache-dir .tools/uv-cache` in place
of `uv`. The downloader uses Python's standard library and adds no dependency.
Each run saves unchanged responses and a manifest under
`data/raw/sentiment/benchmarks/<timestamp>/`. The settings in
`configs/sentiment_benchmarks.json` record source revisions and terms.

FiQA's organizer links were unavailable, so the headline files come from a
challenge-participant mirror. Its test file has no gold scores; it is not a
scored test set. FinEntity's full source includes duplicates and some entity
span/value mismatches, which must be handled during benchmark preparation.
Source snapshots stay local under the Git exclusions. See
[data sources](docs/data_sources.md#sentiment-benchmark-snapshots) for verified
counts and limitations. This command acquires data; it does not evaluate the
model or collect news for the six stocks.

## Run the sentiment study

The [plan](docs/phase_planning/sentiment_plan.md) and
[findings](docs/phase_planning/sentiment_analysis.md) describe the rules and
limitations. No manual sentiment labeling or API key is needed. Acquisition
uses the network; analysis reads saved inputs and model files.

```powershell
uv run --locked python scripts/download_finbert.py
uv run --locked python scripts/run_sentiment.py --stage benchmarks
uv run --locked python scripts/download_google_news.py --pilot
uv run --locked python scripts/download_google_news.py
```

`configs/sentiment.json` selects the benchmark, pilot, and full-news snapshot
paths and pins the model revision. A new download prints its snapshot path;
select that path in the settings before analysis. Inspect the unscored pilot
report and record any collection-rule change before full collection. The
reported run passed with the adopted rules unchanged. To resume a news
snapshot, pass `--resume data/raw/sentiment/google_news/SNAPSHOT`; include
`--pilot` when resuming a pilot. Successful requests are retained.

For the supplied saved snapshots:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
uv run --locked python scripts/run_sentiment.py
uv run --locked jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/06_sentiment.ipynb
uv run --locked python -m unittest discover -s tests -v
```

Use the project-local uv executable/cache on this workstation. The notebook
checks that its kernel is inside `.venv`; restricted sessions may need the
project-local Jupyter/IPython directories described in the master-data section.

Daily/weekly tables are under `data/processed/sentiment/sentiment_v2/`;
metrics and figures are under the corresponding `outputs/` folders. The
`sentiment_v1` folders hold the first run, kept unchanged after the review
corrections described in the findings. The model files stay under
`artifacts/sentiment/sentiment_v1/finbert/` for both runs. Text,
raw responses, and model weights stay local. A later RSS search can return
different items; download instructions alone cannot reproduce the exact
reported news snapshot.

### Offline Docker reproduction

This command uses saved inputs and writes comparison outputs separately.
The source snapshots, model, and market inputs must already exist locally.
The model and raw sentiment files are excluded from the image.

```powershell
docker build -t financial-market-analytics-3:sentiment .
$sentimentDockerOut = Join-Path (Get-Location) '.tools/sentiment_docker_v2'
foreach ($folder in @('interim','processed','metrics','figures')) {
    New-Item -ItemType Directory -Path (Join-Path $sentimentDockerOut $folder) -Force | Out-Null
}
$sentimentDockerArgs = @(
    'run','--name','fma3-sentiment-v2','--network','none',
    '-e','HF_HUB_OFFLINE=1','-e','TRANSFORMERS_OFFLINE=1',
    '-v',"${PWD}/configs/sentiment.json:/workspace/configs/sentiment.json:ro",
    '-v',"${PWD}/data/raw/sentiment:/workspace/data/raw/sentiment:ro",
    '-v',"${PWD}/artifacts/sentiment/sentiment_v1/finbert:/workspace/artifacts/sentiment/sentiment_v1/finbert:ro",
    '-v',"${PWD}/data/processed/master_unseen.csv:/workspace/data/processed/master_unseen.csv:ro",
    '-v',"${PWD}/data/processed/statistical_baseline:/workspace/data/processed/statistical_baseline:ro",
    '-v',"${PWD}/outputs/backtests/statistical_baseline/phase4_v1/unseen:/workspace/outputs/backtests/statistical_baseline/phase4_v1/unseen:ro",
    '-v',"${PWD}/.tools/sentiment_docker_v2/interim:/workspace/data/interim/sentiment/sentiment_v2",
    '-v',"${PWD}/.tools/sentiment_docker_v2/processed:/workspace/data/processed/sentiment/sentiment_v2",
    '-v',"${PWD}/.tools/sentiment_docker_v2/metrics:/workspace/outputs/metrics/sentiment/sentiment_v2",
    '-v',"${PWD}/.tools/sentiment_docker_v2/figures:/workspace/outputs/figures/sentiment/sentiment_v2",
    'financial-market-analytics-3:sentiment','uv','run','--locked',
    '--no-dev','--no-editable','--no-sync','--offline','python','scripts/run_sentiment.py'
)
& docker @sentimentDockerArgs
```

The image was installed with `uv sync --locked`; `--no-sync` preserves that
environment during the network-disabled run. Without it, uv tried to rebuild
the project and could not fetch its uncached build dependency. Choose a new
container name for another run.

The reported comparison preserved the first v2 outputs under
`.tools/sentiment_reference_v2/` before rerunning the notebook and container.
The verification tool compares copies containing `interim/`, `processed/`,
and `metrics/` folders:

```powershell
uv run --locked python tests/verify_sentiment_reproduction.py --reference .tools/sentiment_reference_v2 --actual .tools/sentiment_docker_v2 --report outputs/metrics/sentiment/sentiment_v2/docker_reproduction.json
```

The saved local and Docker reproduction reports record exact discrete and
classification agreement and numerical differences under the `1e-5` bound.
The optional local handoff hash inventory is in `.tools/`; the earlier
phases' public file contracts are checked independently in every run.

## Build Phase 1 master data

The build runs offline from the snapshots pinned in `configs/master_data.json`:

```powershell
uv run --locked python scripts/build_master.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/01_master_data.ipynb
```

Use `.\.tools\uv.exe --cache-dir .tools/uv-cache` in place of `uv` on this
workstation. In a restricted session, the notebook also needs writable Jupyter
and IPython directories. Set these before its execution command:

```powershell
$env:JUPYTER_CONFIG_DIR = Join-Path (Get-Location) '.tools/jupyter/config'
$env:JUPYTER_DATA_DIR = Join-Path (Get-Location) '.tools/jupyter/data'
$env:JUPYTER_RUNTIME_DIR = Join-Path (Get-Location) '.tools/jupyter/runtime'
$env:IPYTHONDIR = Join-Path (Get-Location) '.tools/ipython'
```

The build saves aligned source fields under `data/interim/` and masters under
`data/processed/`: 2,011 historical rows and 145 unseen rows, each with 49
columns including Date. Raw files are unchanged. The manifest records the
input and output hashes, settings, and versions. Quality checks, independent
return calculations, and large-move flags are in `outputs/metrics/phase1_*.csv`.
The [data dictionary](docs/data_dictionary.md) defines every master column.

To build only the historical period without opening Yahoo's unseen files:

```powershell
uv run --locked python scripts/build_master.py --historical-only
```

That command writes historical outputs and replaces the shared audit files
and manifest with the historical run's records. Any older unseen files are
left on disk but are not listed as outputs of that run. Run the full build
again to restore the combined manifest and audit tables. The notebook checks
that both modes produce the same historical master, then leaves a full build
on disk. The unseen master is reserved for later evaluation.

A fresh runtime environment was also checked with the commands below. It
installs only the locked runtime dependencies and reproduces the same outputs:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.tools/phase1-clean-venv'
uv sync --locked --no-dev --python .venv/Scripts/python.exe
uv run --locked --no-dev python scripts/build_master.py
Remove-Item Env:\UV_PROJECT_ENVIRONMENT
```

## Run Phase 2 exploratory analysis

The EDA reads only `data/processed/master_historical.csv`, after checking its
hash against the Phase 1 manifest, so build the master first:

```powershell
uv run --locked python scripts/run_eda.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/02_eda.ipynb
```

The same workstation substitutions and Jupyter variables as for Phase 1 apply.
Settings are in `configs/eda.json`. The script writes ten tables and
`run_metadata.json` to `outputs/metrics/eda/` and nine figures to
`outputs/figures/eda/`; `--no-figures` skips the figures. The run stops if the
input hash, columns, dates, or missing values are not as expected. The
[data dictionary](docs/data_dictionary.md#phase-2-eda-tables) defines the
table columns, and the [Phase 2 analysis](docs/phase_planning/phase_2_analysis.md)
reports the findings.

To run the master build, EDA, and pair selection in one step, as the Docker image does:

```powershell
uv run --locked python scripts/run_pipeline.py
uv run --locked python scripts/run_pipeline.py --historical-only
```

`--historical-only` is passed to the master build, so no Yahoo unseen file is
opened, and it leaves the historical-only manifest described above.

## Run Phase 3 pair selection

Phase 3 reads the historical master and its manifest entry only. Its adopted
settings are in `configs/pair_selection.json`:

```powershell
uv run --locked python scripts/run_pair_selection.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/03_pair_selection.ipynb
```

Use the workstation uv/cache substitutions and Jupyter variables above.
`--no-figures` saves the numeric outputs without drawing plots. The script
fits 30 OLS directions, runs 15 Johansen tests, applies the pair-level
multiple-testing correction, and saves eight metric tables, 15 fitted JSONs,
one historical spread file, and four figures. It stops on invalid input,
failed fits, collinearity warnings, or non-finite statistics. All calculation
and artifact checks must pass before run metadata reports completion.

See the [Phase 3 analysis](docs/phase_planning/phase_3_analysis.md) for the
exploratory shortlist and the
[data dictionary](docs/data_dictionary.md#phase-3-pair-selection-tables-and-spreads)
for column definitions. These outputs contain no unseen evaluation, Z-scores,
or trading results. The batch pipeline now runs Phase 3 after EDA;
`--historical-only` also keeps the preceding master build out of unseen data.

## Run Phase 4 statistical baseline

Phase 4 loads the Phase 3 regressions and estimates normalization from 2025
residuals only. Its settings are in `configs/statistical_baseline.json`:

```powershell
uv run --locked python scripts/run_statistical_baseline.py --historical-only
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/run_statistical_baseline.py
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/04_statistical_baseline.ipynb
```

Use the workstation uv/cache and Jupyter settings above. The standalone script
needs existing masters and Phase 3 outputs. If the manifest currently covers
only historical data, run `scripts/build_master.py` first to include the saved
unseen snapshot. `--historical-only` never opens the unseen master.
`--no-figures` skips plotting.

The first run saves two normalization JSONs. Later runs load and validate them.
Each period produces a spread/Z-score CSV, four backtest tables, three metric
tables, metadata, and three figures. The notebook adds
`unseen/market_exposure.csv`, a single-factor estimate of each unseen trade's
market share. Once unseen outputs exist, changed code,
settings, fitted objects, or unseen input are rejected under that output
version. Preserve the earlier run and record a correction before using another
version; do not remove the evaluation contract to replace a result.

The [Phase 4 analysis](docs/phase_planning/phase_4_analysis.md) explains the
results and limitations. [Column definitions](docs/data_dictionary.md#phase-4-statistical-baseline)
cover the outputs. Returns use separate USD 10,000 accounts; both exploratory
pairs share AMZN. The ordered pipeline now covers Phases 1-4:

```powershell
uv run --locked python scripts/run_pipeline.py --historical-only
uv run --locked python scripts/run_pipeline.py
```

The historical replay is in sample, including its early years. The full run
adds the fixed January-July 2026 evaluation. Neither command downloads data.

## Run Phase 5 LSTM comparison

Phase 5 uses the two exploratory pairs, with 2018-2023 fitting and 2024-2025
validation. Each model predicts five changes from the current Z-score. The
final refit uses the saved Phase 3 OLS and Phase 4 normalization through 2025.
CPU-only torch is resolved through its explicit uv index; the earlier numeric
library versions are retained.

```powershell
uv sync --locked
uv run --locked python scripts/run_lstm_forecast.py --stage select
uv run --locked python scripts/run_lstm_forecast.py --stage refit
uv run --locked python scripts/run_lstm_forecast.py --stage evaluate
```

The standalone runner needs the existing masters and Phase 3/4 handoff. Its
default runs all three stages. `--historical-only` runs selection and refit
without opening unseen inputs; it cannot be combined with `--stage`.
Evaluation loads frozen artifacts and does not train. An evaluated version
rejects changed code, settings, inputs, or artifacts. Preserve a corrected
run under a new version rather than removing that protection.

```powershell
uv run --locked python scripts/run_lstm_forecast.py --historical-only
uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/05_lstm_comparison.ipynb
uv run --locked python -m unittest discover -s tests -v
```

Use the workstation uv/cache and Jupyter environment variables documented
above. The version in `configs/lstm_forecast.json` names the output folders;
the reported run is `phase5_v2`. Forecasts are in
`outputs/predictions/lstm/phase5_v2/`; trial histories, metrics, direction
base rates, filter decisions, and comparison tables are in
`outputs/metrics/lstm/phase5_v2/`. Matched baseline and filtered account
ledgers are under `outputs/backtests/lstm_comparison/phase5_v2/`. The original
full-period Phase 4 baseline remains available in the comparison. The first
evaluated run, `phase5_v1`, is kept unchanged in matching folders.

Final bundles under `artifacts/lstm/phase5_v2/<PAIR_ID>/final_20180102_20251231/`
contain weights, embedded fitted preprocessing, and a known reload example.
`forecast_from_prices` loads a bundle without training. It checks consecutive
sessions against the saved historical calendar. For later dates, supply an
independent expected session calendar through `session_calendar`; deriving
that calendar from the submitted price rows would hide missing sessions.
The API and web interface remain separate work.

The ordered pipeline validates and reuses the Phase 3 handoff when Phase 4
has already frozen it. Regenerating its metadata after adding a dependency
would change the recorded lockfile hash and invalidate the earlier evaluated
run. Fresh Docker builds exclude those objects and reconstruct all five phases.

To reproduce the batch run in Docker, build the image and run both pipeline
modes and the tests. Give each container its own name:

```powershell
docker build -t financial-market-analytics-3 .
docker run --name fma3-historical financial-market-analytics-3 python scripts/run_pipeline.py --historical-only
docker run --name fma3-full financial-market-analytics-3
docker run --rm financial-market-analytics-3 python -m unittest discover -s tests -v
```

Generated files stay inside the containers and can be copied out with
`docker cp` for comparison without replacing local results. Retraining on
Linux gives the same selected models, epochs, and trading decisions as
Windows, but its forecasts differ slightly; reported results use the Windows
CPU artifacts. Verification records are in
`outputs/metrics/phase5_{review,docker}_validation.json`.

## Docker environment

On Windows, Docker Desktop supplies the Linux container engine. If it is not
already running, start it in the background and wait until `docker version`
shows a Server section:

```powershell
Start-Process -FilePath "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
docker version
```

For the earlier pipeline checkout, build the image and run its default batch
command from the project root. The current sentiment run uses the separate
offline command above.

```powershell
docker build -t financial-market-analytics-3 .
docker run --rm financial-market-analytics-3
```

The image creates its own Linux environment from `pyproject.toml` and `uv.lock`;
the Windows `.venv/` is excluded. It runs as an unprivileged user. The default
command is `scripts/run_pipeline.py`: it builds the masters from the copied
snapshots, then runs EDA, pair selection, the statistical baseline, and the
LSTM comparison, and
writes all outputs inside the container.
This is a batch command: exit code 0 means every phase finished. No web server
is implemented yet. A single phase can be run by passing its script, for
example `docker run --rm financial-market-analytics-3 python scripts/build_master.py`. `--rm` removes that
container after it exits; a named container can instead be retained for logs
and inspection:

```powershell
docker run --name financial-market-analytics-3-phase1 financial-market-analytics-3
docker logs financial-market-analytics-3-phase1
docker start --attach financial-market-analytics-3-phase1
```

The Phase 2 check ran the historical-only pipeline in a named container and
copied the EDA tables out for comparison with the Windows run:

```powershell
docker build -t financial-market-analytics-3:phase2-review .
docker run --name financial-market-analytics-3-phase2-review financial-market-analytics-3:phase2-review python scripts/run_pipeline.py --historical-only
docker cp financial-market-analytics-3-phase2-review:/workspace/outputs/metrics/eda <folder outside outputs/>
docker run --rm financial-market-analytics-3:phase2-review python -m unittest discover -s tests
```

The named containers above were created during verification. `docker start`
reruns its build. Outputs stay in the container; the local masters are not
overwritten. The image excludes local agent files, supplied assignment
material, IBKR data, and previously generated datasets and outputs. It must
therefore build the masters from the permitted raw snapshots.

Phase 3 was verified on 1 November 2026 with these commands:

```powershell
docker build -t financial-market-analytics-3:phase3-20261101-tidy .
docker run --name financial-market-analytics-3-phase3-20261101-tidy financial-market-analytics-3:phase3-20261101-tidy python scripts/run_pipeline.py --historical-only
docker run --rm financial-market-analytics-3:phase3-20261101-tidy python -m unittest discover -s tests -v
```

The pipeline exited with code 0 and all 43 tests passed in the image. The
image excludes previously fitted Phase 3 parameters as well as derived data
and outputs, so the run produces its own files. The eight new metric tables,
15 fitted JSONs, and historical spread grid match the local run within
`rtol=1e-7`, `atol=1e-9`; decisions and labels match exactly. Copy and
comparison details are in `outputs/metrics/phase3_docker_validation.json`.
Its processed directory contains only the historical master, manifest, and
historical spreads. Local review and independent calculation evidence is in
`outputs/metrics/phase3_review_validation.json`.

Phase 4 was verified on 1 November 2026 with both pipeline modes:

```powershell
docker build -t financial-market-analytics-3:phase4-20261101 .
docker run --name financial-market-analytics-3-phase4-historical-20261101 financial-market-analytics-3:phase4-20261101 python scripts/run_pipeline.py --historical-only
docker run --name financial-market-analytics-3-phase4-full-20261101 financial-market-analytics-3:phase4-20261101
docker run --rm financial-market-analytics-3:phase4-20261101 python -m unittest discover -s tests -v
```

Both pipelines exited with code 0 and all 55 tests passed. Derived data,
outputs, and fitted Phase 3/4 artifacts are excluded from the image so the
containers build their own. The historical-only container has no unseen
master or Phase 4 unseen outputs. Copy results from a named container with
`docker cp`, using a separate comparison folder. Numeric values agree with
Windows within `rtol=1e-7`, `atol=1e-9`; signals, directions, trade dates,
and statuses match exactly. Details are in
`outputs/metrics/phase4_docker_validation.json`.

To open a Python session instead:

```powershell
docker run --rm -it financial-market-analytics-3 python
```

The Dockerfile pins Python and uv versions; its base images are version-tagged,
not digest-pinned. The Phase 1 image was built and run on 25 October 2026 with
Docker Engine 29.8.2. It exited with code 0, passed all 13 offline tests, and
produced the same eight CSV hashes as Windows. The 64 data-quality checks also
passed. The evidence is in `outputs/metrics/phase1_docker_validation.json`.
At that verification, the container's build manifest was byte-identical to the
Windows one. Phase 2's dependency changes later changed the manifest's build-file
hashes; the eight Phase 1 CSV hashes stayed the same. Build files
are hashed by package path, so the module is recorded even though the container
installs the package outside the project folder.

The corrected Phase 2 image was run the same day with the historical-only pipeline. It
exited with code 0, all 22 EDA checks and 31 offline tests passed, and the
container held no unseen master. Its rebuilt historical master has the same
hash as the Windows file. Five EDA tables are byte-identical and the other
five differ by at most 1.3e-15, within the recorded 1e-9 tolerance. The
evidence is in `outputs/metrics/phase2_docker_validation.json`. The default full
pipeline also exited with code 0. The notebook rerun and independent numerical
checks are recorded in `outputs/metrics/phase2_review_validation.json`.

In the coding-agent sandbox, Docker's API and configuration file were
inaccessible. Running Docker commands outside the sandbox resolved that
restriction. Docker Desktop was already running; no restart was needed.
API and web commands will be documented as those components are
implemented. Follow the official
[uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) when
extending the environment.

## Start here

- [Directory guide](docs/directory_guide.md): every folder's role and the files
  to add during implementation.
- [Submission requirements](docs/submission_requirements.md): packaging,
  reproducibility, API, and deliverable requirements.

Serving commands will be added after implementation and verification.

## Submission

Prepare one compressed folder containing the required code, configuration,
documentation, fitted models and preprocessing objects, and final results.
Exclude credentials, local environments, caches, and unused experiments.
Use the checklist in `docs/submission_requirements.md` before packaging.
