# Financial Market Analytics

A postgraduate technology-stock analytics project.

## Current status

Phase 1 produces validated historical and unseen master datasets from the
pinned Yahoo and Cboe snapshots. The build, audit tables, and executed notebook
are implemented. EDA, pair selection, models, API, and web interface remain.
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
does not. Runtime dependencies currently include yfinance and pandas.

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

## Docker environment

On Windows, Docker Desktop supplies the Linux container engine. If it is not
already running, start it in the background and wait until `docker version`
shows a Server section:

```powershell
Start-Process -FilePath "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
docker version
```

Build and run the Phase 1 container from the project root:

```powershell
docker build -t financial-market-analytics-3 .
docker run --rm financial-market-analytics-3
```

The image creates its own Linux environment from `pyproject.toml` and `uv.lock`;
the Windows `.venv/` is excluded. It runs as an unprivileged user. The default
command runs the Phase 1 build from the copied snapshots and writes its outputs
inside the container. This is a batch command: exit code 0 means the data build
finished successfully. No web server is implemented yet. `--rm` removes that
container after it exits; a named container can instead be retained for logs
and inspection:

```powershell
docker run --name financial-market-analytics-3-phase1 financial-market-analytics-3
docker logs financial-market-analytics-3-phase1
docker start --attach financial-market-analytics-3-phase1
```

The named container above was created during verification. `docker start`
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
The container's build manifest is byte-identical to the Windows one. Build files
are hashed by package path, so the module is recorded even though the container
installs the package outside the project folder.

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
