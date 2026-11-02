"""Serve the saved Phase 5 LSTMs on the project's session calendar."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from market_analytics.api.analysis import order_tickers
from market_analytics.api.prices import InputError, tickers as price_tickers
from market_analytics.models.forecasting import forecast_from_prices
from market_analytics.trading.baseline import apply_normalization, spread_from_prices

HORIZON = 5
NOTE = ("On the unseen January-July 2026 sessions, a persistence forecast (Z stays where it is) "
        "was more accurate than this LSTM, so treat the path as illustrative.")


class BundleUnavailable(RuntimeError):
    """The pair has a bundle, but it failed its startup check."""


def known_prices(known):
    frame = pd.DataFrame(known["prices"])
    return frame.assign(Date=pd.to_datetime(frame["Date"])).set_index("Date")


def check_bundle(pair_id, directory, tolerance):
    """Reproduce the bundle's saved example forecast; a changed model.pt fails inside forecast_from_prices."""
    entry = {"pair_id": pair_id, "directory": str(directory), "status": "failed", "error": None,
             "model_version": None, "max_abs_difference": None, "meta": None}
    try:
        meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        known = json.loads((directory / "known_inference.json").read_text(encoding="utf-8"))
        if meta["pair"]["pair_id"] != pair_id:
            raise ValueError(f"metadata names pair {meta['pair']['pair_id']}")
        served = forecast_from_prices(known_prices(known), directory)
        difference = float(np.max(np.abs(served - np.asarray(known["forecast_z"]))))
        entry.update(model_version=meta["model_version"], max_abs_difference=difference, meta=meta)
        if difference > tolerance:
            raise ValueError(f"example forecast differs by {difference:.3g}")
        entry["status"] = "ok"
    except Exception as exc:  # any failure only disables this bundle; the statistical routes stay up
        entry["error"] = f"{type(exc).__name__}: {exc}"
    return entry


def load_registry(root, bundles, tolerance):
    return {pair_id: check_bundle(pair_id, Path(root) / relative, tolerance)
            for pair_id, relative in bundles.items()}


def check_sessions(index, calendar, min_sessions, last_origin):
    """Reject histories the model was not built for, with a message naming the first problem."""
    if len(index) < min_sessions:
        raise InputError(f"{len(index)} sessions supplied; the forecast needs at least {min_sessions}")
    origin = index[-1]
    if origin > last_origin:
        raise InputError(f"The last date {origin.date()} is after {last_origin.date()}, "
                         "the last session in the project calendar")
    if index[0] < calendar[0]:
        raise InputError(f"{index[0].date()} is before the project calendar starts on {calendar[0].date()}")
    unknown = index.difference(calendar)
    if len(unknown):
        raise InputError(f"{unknown[0].date()} is not a trading session in the project calendar")
    expected = calendar[(calendar >= index[0]) & (calendar <= origin)]
    missing = expected.difference(index)
    if len(missing):
        raise InputError(f"Session {missing[0].date()} is missing from the prices")


def forecast_pair(prices, registry, calendar, settings):
    """Five-session Z forecast from the last supplied close, using the bundle's own fit."""
    pair_id = "_".join(order_tickers(price_tickers(prices)))
    if pair_id not in registry:
        raise InputError(f"No saved model for {pair_id}; forecasts exist for {', '.join(sorted(registry))}")
    bundle = registry[pair_id]
    if bundle["status"] != "ok":
        raise BundleUnavailable(f"The {pair_id} model failed its startup check: {bundle['error']}")
    calendar = pd.DatetimeIndex(calendar)
    last_origin = pd.Timestamp(settings["last_calendar_session"])
    check_sessions(prices.index, calendar, settings["min_sessions"], last_origin)
    meta = bundle["meta"]
    forecast = forecast_from_prices(prices, bundle["directory"], session_calendar=calendar)
    origin = prices.index[-1]
    origin_z = float(apply_normalization(spread_from_prices(prices, meta["ols"]), meta["normalization"]).iloc[-1])
    later = calendar[calendar > origin][:HORIZON]
    change = float(forecast[-1]) - origin_z
    return {
        "pair_id": pair_id, "model_version": meta["model_version"],
        "dependent": meta["pair"]["dependent"], "independent": meta["pair"]["independent"],
        "training_end": meta["training_sessions"][-1],
        "origin": str(origin.date()), "origin_z": origin_z,
        # Targets past the project calendar have no known session date.
        "forecasts": [{"horizon": h + 1, "target_date": str(later[h].date()) if h < len(later) else None,
                       "forecast_z": float(forecast[h])} for h in range(HORIZON)],
        "day_five_change": change, "day_five_direction": "up" if change > 0 else "down" if change < 0 else "flat",
        "note": NOTE,
    }
