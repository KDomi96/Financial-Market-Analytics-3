# Financial Market Analytics

A postgraduate technology-stock analytics project.

## Current status

Yahoo Finance daily data have been downloaded for the six stocks, S&P 500,
and VIX. A reproducible acquisition command and data validation checks are
implemented. Cleaning, master-data construction, notebooks, models, API, and
web interface remain to be implemented. The Python 3.12.13 environment is
managed with uv. Docker configuration is provided for the environment.

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

The acquisition checks have a small offline test suite:

```powershell
uv run --locked python -m unittest discover -s tests -v
```

See [data sources and acquisition results](docs/data_sources.md), including
VIX holiday records that must be handled during later alignment. Downloading
data does not fit models or use the unseen period for analytical decisions.

## Docker environment

With Docker installed and its Linux container engine running:

```powershell
docker build -t financial-market-analytics-3 .
docker run --rm financial-market-analytics-3
```

The image creates its own Linux environment from `pyproject.toml` and `uv.lock`;
the Windows `.venv/` is excluded. It runs as an unprivileged user. The default
command imports the package, prints the scaffold status, and exits. It does not
start a web server. To open a Python session instead:

```powershell
docker run --rm -it financial-market-analytics-3 python
```

The Dockerfile pins Python and uv versions; its base images are version-tagged,
not digest-pinned. The acquisition command above has been exercised in the
local venv; it has not been tested inside Docker. Training, API, and web commands
will be documented as those components are implemented. Follow the official
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
