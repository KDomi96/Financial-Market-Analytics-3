# Running the API and the interface

The service has two parts. The FastAPI app in `src/market_analytics/api/`
does every calculation, and the Streamlit page in `app/streamlit_app.py` sends
it requests and draws the answers. Both read saved files and write none. The
design is in [methodology](methodology.md#api-and-web-application).

## Files the service needs

The API refuses to start without these, and checks the two masters against
the hashes in the manifest:

- `data/processed/master_historical.csv`, `master_unseen.csv`, and
  `master_manifest.json` (prices for the sample route and the session calendar)
- `outputs/metrics/pair_selection/pair_ranking.csv` (Phase 3 labels)
- `configs/api.json`, `configs/pair_selection.json`, and
  `configs/statistical_baseline.json`

The two LSTM bundles under `artifacts/lstm/phase5_v2/` are checked at startup.
If one is missing or its `model.pt` hash has changed, the API still starts,
`/health` reports `degraded` with the reason, and only that pair's forecasts
return 503.

## Local run

From the project root, in two terminals:

```powershell
uv run --locked uvicorn market_analytics.api.main:app --port 8000
uv run --locked streamlit run app/streamlit_app.py
```

The page opens on `http://localhost:8501` and the API documentation on
`http://localhost:8000/docs`. The page finds the API through `API_URL`, which
defaults to `http://localhost:8000`; `.env.example` lists it. The API reads
`configs/api.json` relative to the working directory, or the file named in
`API_CONFIG`.

If a conda environment is active, uv prints a warning that `VIRTUAL_ENV` does
not match `.venv` and then uses `.venv` anyway. Running `conda deactivate`
first removes the warning.

## Docker Compose

From the project root, with Docker Desktop running:

```powershell
docker compose up -d
docker compose ps
docker compose down
```

`compose.yaml` builds the project image and starts two containers from it.
The `api` service runs Uvicorn on port 8000; the `app` service runs Streamlit
on port 8501 and waits until the API passes its health check. The app reaches
the API at `http://api:8000` inside the Compose network, so only the page and
the API documentation need to be opened from the browser. The image leaves out
the saved data and models, so Compose mounts `data/processed/`,
`artifacts/lstm/phase5_v2/`, and `outputs/metrics/pair_selection/` read-only
from the project folder. Those folders must be present, as they are in the
submission archive.

I verified this with Docker Engine 29.8.2. Both services
started, the models reloaded on Linux within 1.5e-8 of their saved examples,
`/analyze` on AMZN_META gave the same result as on Windows, and a write to a
mounted folder was refused. The record is
`outputs/metrics/phase6_docker_validation.json`.

## Routes

| Route | Input | Result |
| --- | --- | --- |
| `GET /health` | none | `ok`, or `degraded` with the failed bundle and its error |
| `GET /pairs` | none | The six tickers, the 15 pairs with their Phase 3 rank and label, and which have a forecast model |
| `GET /samples/{pair_id}` | a pair from `/pairs`, e.g. `AMZN_META` | CSV of the pair's 2,156 closes in the upload format; 404 otherwise |
| `POST /analyze` | multipart `file`, optional `fit_end` (default 2025-12-31) and `exploratory` | Test results; spread, Z-scores, and signals when the pair passes or the exploratory view is asked for; 422 with a message for bad input |
| `POST /forecast` | multipart `file`, optional `pair` and `origin` | Five-session Z forecast from the saved model; 422 for bad input or a pair without a model, 503 if its model failed the startup check |

For example, with the API running:

```powershell
curl.exe -s http://localhost:8000/samples/AMZN_META -o AMZN_META.csv
curl.exe -s -X POST -F "file=@AMZN_META.csv" -F "fit_end=2025-12-31" http://localhost:8000/analyze
curl.exe -s -X POST -F "file=@AMZN_META.csv" -F "origin=2026-03-16" http://localhost:8000/forecast
```

An uploaded file needs the header `Date,<TICKER_A>,<TICKER_B>`, dates as
`YYYY-MM-DD` in increasing order, and a positive closing price in every cell.
It may be at most 1 MiB and 10,000 rows. Anything else is rejected with the
line number of the first problem.

## Hosting

No hosted deployment exists, and no public URL is claimed. A host would need
its own copy of the saved files listed above, because the image leaves them
out.
