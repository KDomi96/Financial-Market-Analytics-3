# Financial Market Analytics

A postgraduate technology-stock analytics project.

## Current status

The directory scaffold is prepared. No data have been downloaded, no models
have been fitted, and no executable pipeline, API, or web interface exists yet.
The Python 3.12.13 environment and installable package skeleton are configured
with uv. Analytical dependencies will be added as their components are built.
Docker configuration is provided for the environment; it does not yet run an
analysis pipeline or application.

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
does not. There are currently no third-party runtime dependencies.

On this workstation, uv is available as the project-local `.tools/uv.exe`.
Use `.\.tools\uv.exe` in place of `uv` in the commands above if uv is not on PATH.
The tool directory is ignored by Git and Docker and is not a submission file.

Use `uv add PACKAGE` to add a runtime dependency or `uv add --dev PACKAGE` for a
development tool. These commands update both dependency files. Use `uv run` for
project commands so they execute inside the project environment. PowerShell
activation is optional: `.\.venv\Scripts\Activate.ps1`.

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
not digest-pinned. Data acquisition, training, API, and web commands will be
documented and added as those components are implemented. Follow the official
[uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) when
extending the environment.

## Start here

- [Directory guide](docs/directory_guide.md): every folder's role and the files
  to add during implementation.
- [Submission requirements](docs/submission_requirements.md): packaging,
  reproducibility, API, and deliverable requirements.

Exact installation and execution commands will be added after their corresponding
components are implemented and verified.

## Submission

Prepare one compressed folder containing the required code, configuration,
documentation, fitted models and preprocessing objects, and final results.
Exclude credentials, local environments, caches, and unused experiments.
Use the checklist in `docs/submission_requirements.md` before packaging.
