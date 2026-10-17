"""Download dated Yahoo Finance snapshots without cleaning or fitting models."""

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yfinance as yf


PRICE_FIELDS = ["Open", "High", "Low", "Close", "Adj Close"]
REQUIRED_FIELDS = PRICE_FIELDS + ["Volume"]


def inspect_prices(frame: pd.DataFrame, period: dict, reference_dates: set | None = None) -> dict:
    """Check provider records without changing, imputing, or dropping rows."""
    errors = []
    missing = sorted(set(REQUIRED_FIELDS) - set(frame.columns))
    dates = pd.DatetimeIndex(frame.index)
    # Use exchange-local calendar dates, not UTC conversion across midnight.
    dates = dates.tz_localize(None).normalize()
    if frame.empty:
        errors.append("Empty download")
    if missing:
        errors.append(f"Missing required fields: {missing}")
    if dates.hasnans:
        errors.append("Invalid dates")
    if dates.has_duplicates:
        errors.append("Duplicate trading dates")
    if not dates.is_monotonic_increasing:
        errors.append("Dates are not increasing")
    if len(dates):
        if ((dates < pd.Timestamp(period["start"])) |
                (dates >= pd.Timestamp(period["end_exclusive"]))).any():
            errors.append("Observations outside the requested period")
        if dates.min() != pd.Timestamp(period["first_session"]):
            errors.append("First expected trading session is missing")
        if dates.max() != pd.Timestamp(period["last_session"]):
            errors.append("Last expected trading session is missing")
    # Yahoo VIX includes empty holiday rows with keepna=True. Recognize only
    # completely empty prices on dates absent from the stock benchmark.
    empty_nontrading = pd.Series(False, index=frame.index)
    if reference_dates is not None and not missing:
        empty_nontrading = (frame[PRICE_FIELDS].isna().all(axis=1)
                            & frame["Volume"].eq(0)
                            & ~pd.Series(dates.date, index=frame.index).isin(reference_dates))
    observed = frame.loc[~empty_nontrading]
    present = [field for field in REQUIRED_FIELDS if field in frame]
    null_counts = {field: int(frame[field].isna().sum()) for field in present}
    if observed[present].isna().any().any():
        errors.append("Missing OHLCV or adjusted-close values")
    if not missing:
        if not observed[REQUIRED_FIELDS].map(
            lambda value: pd.notna(value) and float("-inf") < value < float("inf")
        ).all().all():
            errors.append("Non-finite market values")
        if (frame[PRICE_FIELDS] <= 0).any().any():
            errors.append("Nonpositive prices")
        if (frame["Volume"] < 0).any():
            errors.append("Negative volume")
        if ((frame["High"] < frame[["Open", "Low", "Close"]].max(axis=1)) |
                (frame["Low"] > frame[["Open", "High", "Close"]].min(axis=1))).any():
            errors.append("Inconsistent OHLC bounds")
    return {
        "rows": len(frame),
        "first_date": str(dates.min().date()) if len(dates) else None,
        "last_date": str(dates.max().date()) if len(dates) else None,
        "fields": list(frame.columns),
        "missing_values": null_counts,
        "empty_nontrading_dates": [str(day) for day in dates[empty_nontrading].date],
        "valid_close_rows": int(frame["Close"].notna().sum()) if "Close" in frame else 0,
        "duplicate_dates": int(dates.duplicated().sum()),
        "errors": errors,
    }


def download_snapshot(config_path: Path) -> Path:
    """Save every download plus a manifest; fail visibly on incomplete records."""
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    started = datetime.now(timezone.utc)
    run_dir = project_root / "data/raw/yahoo_finance" / started.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    # Keep yfinance's cookie/timezone cache in an ignored, writable location.
    yf.set_tz_cache_location(str(project_root / ".tools/yfinance-cache"))
    settings = {
        "interval": "1d", "auto_adjust": False, "back_adjust": False,
        "actions": True, "repair": False, "keepna": True,
        "prepost": False, "rounding": False, "threads": False,
        "ignore_tz": True, "multi_level_index": False,
        "progress": False, "timeout": 30,
    }
    manifest = {
        "provider": "Yahoo Finance", "access_library": "yfinance",
        "started_at_utc": started.isoformat(),
        "versions": {name: version(name) for name in ["yfinance", "pandas", "numpy"]},
        "python": platform.python_version(), "configuration": config,
        "download_settings": settings,
        "representation": "CSV serialization of yfinance-returned records; not raw HTTP payloads",
        "adjustment_policy": (
            "Preserve Close and Adj Close as supplied. auto_adjust=False does not "
            "undo Yahoo's existing split adjustments. No additional adjustment, "
            "repair, imputation, filtering, or rounding is applied. Analytical "
            "price choice and P&L treatment remain to be established."
        ),
        "records": [], "errors": [], "status": "interrupted",
    }
    try:
        for period_name, period in config["periods"].items():
            period_dir = run_dir / period_name
            period_dir.mkdir()
            date_sets = {}
            for symbol, name in config["instruments"].items():
                record = {"period": period_name, "symbol": symbol, "name": name}
                manifest["records"].append(record)
                try:
                    for attempt in range(1, 4):
                        try:
                            frame = yf.download(symbol, start=period["start"],
                                                end=period["end_exclusive"], **settings)
                            if frame is None or frame.empty:
                                raise RuntimeError("Yahoo returned no observations")
                            break
                        except Exception:
                            if attempt == 3:
                                raise
                            time.sleep(2 ** attempt)
                    path = period_dir / f"{symbol.removeprefix('^')}.csv"
                    frame.to_csv(path, index_label="Date")
                    record.update({
                        "file": path.relative_to(run_dir).as_posix(),
                        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                        "attempts": attempt,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "validation": inspect_prices(
                            frame, period,
                            reference_dates=date_sets.get("^GSPC") if symbol == "^VIX" else None,
                        ),
                    })
                    date_sets[symbol] = set(pd.DatetimeIndex(frame.index).date)
                    record["valid_close_dates"] = sorted(
                        str(day) for day in pd.DatetimeIndex(frame.loc[frame["Close"].notna()].index).date
                    ) if symbol == "^VIX" else None
                    for error in record["validation"]["errors"]:
                        manifest["errors"].append(f"{period_name}/{symbol}: {error}")
                    print(f"{period_name:10} {symbol:6} {len(frame):5} rows "
                          f"{record['validation']['first_date']} to "
                          f"{record['validation']['last_date']}", flush=True)
                except Exception as exc:
                    record["error"] = str(exc)
                    manifest["errors"].append(f"{period_name}/{symbol}: {exc}")
                    print(f"FAILED {period_name}/{symbol}: {exc}", flush=True)
            reference = date_sets.get("^GSPC")
            if reference is not None:
                for record in manifest["records"]:
                    if record["period"] != period_name or record["symbol"] not in date_sets:
                        continue
                    dates = date_sets[record["symbol"]]
                    record["calendar_vs_sp500"] = {
                        "missing_dates": sorted(str(day) for day in reference - dates),
                        "extra_dates": sorted(str(day) for day in dates - reference),
                    }
                    # VIX can have a different publication calendar; report it.
                    if record["symbol"] != "^VIX" and dates != reference:
                        manifest["errors"].append(
                            f"{period_name}/{record['symbol']}: dates differ from S&P 500"
                        )
                    if record["symbol"] == "^VIX":
                        valid_dates = set(record.pop("valid_close_dates"))
                        reference_strings = {str(day) for day in reference}
                        record["calendar_vs_sp500"]["missing_valid_close_dates"] = sorted(
                            reference_strings - valid_dates
                        )
                        record["calendar_vs_sp500"]["extra_valid_close_dates"] = sorted(
                            valid_dates - reference_strings
                        )
                        if reference_strings - valid_dates:
                            manifest["errors"].append(f"{period_name}/^VIX: missing prices on S&P 500 dates")
        manifest["status"] = "failed" if manifest["errors"] else "complete"
    finally:
        manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Snapshot: {run_dir.relative_to(project_root)}", flush=True)
    if manifest["errors"]:
        raise RuntimeError("Download validation failed; inspect manifest.json: "
                           + "; ".join(manifest["errors"]))
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path("configs/yahoo_finance.json"))
    args = parser.parse_args()
    download_snapshot(args.config)


if __name__ == "__main__":
    main()
