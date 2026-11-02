"""FastAPI app. This is the only service module that reads files; it never writes any."""

import json
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from market_analytics.api import schemas
from market_analytics.api.analysis import analyse_pair, order_tickers
from market_analytics.api.forecast import BundleUnavailable, forecast_pair, load_registry
from market_analytics.api.prices import InputError, parse_prices, tickers as price_tickers
from market_analytics.cointegration.selection import stock_pairs
from market_analytics.data.master import STOCKS, project_path, sha256


def read_json(root, relative):
    return json.loads(project_path(root, relative).read_text(encoding="utf-8"))


def load_state(config_path, **overrides):
    """Read settings, check the masters against the manifest, and run the bundle startup checks."""
    path = Path(config_path).resolve()
    root = path.parent.parent
    cfg = {**json.loads(path.read_text(encoding="utf-8")), **overrides}
    manifest = read_json(root, cfg["manifest"])
    frames = []
    for key in ("historical", "unseen"):
        relative = cfg[key]
        if sha256(project_path(root, relative)) != manifest["outputs"].get(relative):
            raise RuntimeError(f"{relative} does not match the hash in the master manifest")
        frames.append(pd.read_csv(project_path(root, relative), parse_dates=["Date"],
                                  usecols=["Date", *[f"{s}_Close" for s in STOCKS]]).set_index("Date"))
    prices = pd.concat(frames)
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise RuntimeError("The two masters do not form one ordered session calendar")
    return {
        "cfg": cfg, "prices": prices,
        "pair_cfg": read_json(root, cfg["pair_selection_config"]),
        "rules": read_json(root, cfg["statistical_baseline_config"])["rules"],
        "ranking": pd.read_csv(project_path(root, cfg["pair_ranking"])),
        "registry": load_registry(root, cfg["bundles"], cfg["startup_tolerance"]),
    }


def project_pairs():
    return {f"{a}_{b}": (a, b) for a, b in stock_pairs(STOCKS)}


async def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise InputError(f"The file is larger than {max_bytes} bytes")
    return content


def create_app(config_path=None, **overrides):
    config_path = config_path or os.environ.get("API_CONFIG", "configs/api.json")
    state = {}

    @asynccontextmanager
    async def lifespan(app):
        state.update(load_state(config_path, **overrides))
        yield
        state.clear()

    app = FastAPI(title="Pair analysis API", version="phase6_v1", lifespan=lifespan,
                  description="Cointegration test, spread, Z-scores, and Phase 4 signals for a "
                              "supplied price pair, plus the saved Phase 5 LSTM forecasts.")

    @app.exception_handler(InputError)
    async def input_error(request: Request, exc: InputError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(BundleUnavailable)
    async def bundle_error(request: Request, exc: BundleUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health", response_model=schemas.Health)
    def health():
        bundles = [{k: entry[k] for k in ("pair_id", "status", "model_version", "max_abs_difference", "error")}
                   for entry in state["registry"].values()]
        return {"status": "ok" if all(b["status"] == "ok" for b in bundles) else "degraded",
                "bundles": bundles}

    @app.get("/pairs", response_model=schemas.Pairs)
    def pairs():
        ranking = state["ranking"].set_index("pair_id")
        index = state["prices"].index
        return {"tickers": list(STOCKS), "default_fit_end": state["cfg"]["analysis"]["default_fit_end"],
                "first_session": str(index[0].date()), "last_session": str(index[-1].date()),
                "pairs": [{"pair_id": pair_id, "tickers": [a, b], "rank": int(ranking.at[pair_id, "rank"]),
                           "evidence_label": ranking.at[pair_id, "evidence_label"],
                           "dependent": ranking.at[pair_id, "dependent"],
                           "independent": ranking.at[pair_id, "independent"],
                           "has_forecast_model": pair_id in state["registry"]}
                          for pair_id, (a, b) in project_pairs().items()]}

    @app.get("/samples/{pair_id}", response_class=Response,
             responses={200: {"content": {"text/csv": {}}}})
    def sample(pair_id: str):
        if pair_id not in project_pairs():
            raise HTTPException(404, f"Unknown pair {pair_id}; use one of the 15 pairs from /pairs")
        a, b = project_pairs()[pair_id]
        frame = state["prices"][[f"{a}_Close", f"{b}_Close"]].set_axis([a, b], axis=1)
        frame.index = frame.index.strftime("%Y-%m-%d")
        return Response(frame.to_csv(index_label="Date", lineterminator="\n"), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{pair_id}.csv"'})

    @app.post("/analyze", response_model=schemas.Analysis)
    async def analyze(file: UploadFile = File(...), fit_end: str = Form(None), exploratory: bool = Form(False)):
        cfg = state["cfg"]
        content = await read_upload(file, cfg["upload"]["max_bytes"])
        fit_end = fit_end or cfg["analysis"]["default_fit_end"]
        try:
            fit_day = date.fromisoformat(fit_end)
        except ValueError as exc:
            raise InputError(f"fit_end {fit_end!r} is not a YYYY-MM-DD date") from exc
        prices = parse_prices(content, cfg["upload"]["max_bytes"], cfg["upload"]["max_rows"])
        # The tests are CPU work; run them off the event loop.
        return await run_in_threadpool(
            analyse_pair, prices, str(fit_day), state["pair_cfg"], state["rules"], cfg["analysis"],
            exploratory=exploratory, ranking=state["ranking"])

    @app.post("/forecast", response_model=schemas.Forecast)
    async def forecast(file: UploadFile = File(...), pair: str = Form(None), origin: str = Form(None)):
        cfg = state["cfg"]
        content = await read_upload(file, cfg["upload"]["max_bytes"])
        prices = parse_prices(content, cfg["upload"]["max_bytes"], cfg["upload"]["max_rows"])
        supplied = "_".join(order_tickers(price_tickers(prices)))
        if pair and pair != supplied:
            raise InputError(f"The file holds {supplied}, not {pair}")
        if origin:
            # Forecasting from an earlier session uses only the rows up to it.
            try:
                day = pd.Timestamp(date.fromisoformat(origin))
            except ValueError as exc:
                raise InputError(f"origin {origin!r} is not a YYYY-MM-DD date") from exc
            if day not in prices.index:
                raise InputError(f"origin {origin} is not a date in the file")
            prices = prices.loc[:day]
        return await run_in_threadpool(forecast_pair, prices, state["registry"], state["prices"].index,
                                       cfg["forecast"])

    return app


app = create_app()
