# Financial Market Analytics

A postgraduate technology-stock analytics project.

## Current status

Phase 1 produces validated historical and unseen master datasets from the
pinned Yahoo and Cboe snapshots. Phase 2 describes the historical master:
return and risk, all 15 stock pairs, S&P 500 sensitivity, stability over time,
and VIX context. Pair selection, models, API, and web interface remain.
The Python 3.12.13 environment is managed with uv. Docker configuration is
provided for the environment.

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
matplotlib, and statsmodels.

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

To run the master build and the EDA in one step, as the Docker image does:

```powershell
uv run --locked python scripts/run_pipeline.py
uv run --locked python scripts/run_pipeline.py --historical-only
```

`--historical-only` is passed to the master build, so no Yahoo unseen file is
opened, and it leaves the historical-only manifest described above.

## Docker environment

On Windows, Docker Desktop supplies the Linux container engine. If it is not
already running, start it in the background and wait until `docker version`
shows a Server section:

```powershell
Start-Process -FilePath "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
docker version
```

Build the image and run the default pipeline from the project root:

```powershell
docker build -t financial-market-analytics-3 .
docker run --rm financial-market-analytics-3
```

The image creates its own Linux environment from `pyproject.toml` and `uv.lock`;
the Windows `.venv/` is excluded. It runs as an unprivileged user. The default
command is `scripts/run_pipeline.py`: it builds the masters from the copied
snapshots, then runs the EDA, and writes all outputs inside the container.
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
Training, API, and web commands will be documented as those components are
implemented. Follow the official
[uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) when
extending the environment.

## Start here

- [Directory guide](docs/directory_guide.md): every folder's role and the files
  to add during implementation.
- [Submission requirements](docs/submission_requirements.md): packaging,
  reproducibility, API, and deliverable requirements.

Commands for later analytical components will be added after implementation
and verification.

## Submission

Prepare one compressed folder containing the required code, configuration,
documentation, fitted models and preprocessing objects, and final results.
Exclude credentials, local environments, caches, and unused experiments.
Use the checklist in `docs/submission_requirements.md` before packaging.
