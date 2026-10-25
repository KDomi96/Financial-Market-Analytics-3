"""Build separate historical and unseen masters from the pinned snapshots."""

import argparse
import csv
import hashlib
import json
import math
import platform
from decimal import Decimal
from pathlib import Path

import pandas as pd


STOCKS = ("MSFT", "GOOGL", "NVDA", "AAPL", "AMZN", "META")
OHLC = ["Open", "High", "Low", "Close"]
STOCK_FIELDS = OHLC + ["Adj Close", "Volume", "Dividends", "Stock Splits"]
EXCLUSION_FIELDS = ["Date", "Period", "Instrument", "Reason"]
QUALITY_FIELDS = ["Period", "Instrument", "Check", "Status", "Count", "Details"]
MOVE_FIELDS = ["Date", "Period", "Symbol", "Return", "Note", "Source"]
SAMPLE_FIELDS = ["Period", "Symbol", "Date", "PreviousDate", "PreviousClose", "Close",
                 "ExpectedReturn", "ActualReturn", "AbsoluteError"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError(f"Path must stay inside the project: {relative}")
    return path


def master_columns() -> list[str]:
    fields = ["Open", "High", "Low", "Close", "AdjClose", "Volume", "Return"]
    return [f"{symbol}_{field}" for symbol in STOCKS for field in fields] + [
        "GSPC_Close", "GSPC_Return", "VIX_Close", "Year", "Quarter", "Month",
    ]


def validate_source(frame: pd.DataFrame, name: str, *, stock: bool = False,
                    benchmark: bool = False) -> None:
    """Reject invalid source records without changing or filling any values."""
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{name}: expected nonempty daily records")
    if (frame.index.hasnans or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing
            or frame.index.tz is not None
            or not frame.index.equals(frame.index.normalize())):
        raise ValueError(f"{name}: dates must be unique, increasing, and timezone-free daily dates")
    required = STOCK_FIELDS if stock or benchmark else OHLC
    if not set(required).issubset(frame.columns):
        raise ValueError(f"{name}: missing required columns {sorted(set(required) - set(frame.columns))}")
    price_fields = OHLC + (["Adj Close"] if stock or benchmark else [])
    prices = frame[price_fields]
    if not (prices.gt(0) & prices.lt(float("inf"))).all().all():
        raise ValueError(f"{name}: required prices must be finite and positive; no filling is allowed")
    if not (frame["High"].ge(frame[["Open", "Close", "Low"]].max(axis=1))
            & frame["Low"].le(frame[["Open", "Close", "High"]].min(axis=1))).all():
        raise ValueError(f"{name}: inconsistent OHLC prices")
    if stock:
        volume = frame["Volume"]
        if not (volume.gt(0) & volume.lt(float("inf")) & volume.mod(1).eq(0)).all():
            raise ValueError(f"{name}: stock volume must be a positive whole number")
    if stock or benchmark:
        actions = frame[["Dividends", "Stock Splits"]]
        if not (actions.ge(0) & actions.lt(float("inf"))).all().all():
            raise ValueError(f"{name}: invalid dividend or split records")


def align_sources(stocks: dict[str, pd.DataFrame], benchmark: pd.DataFrame,
                  vix: pd.DataFrame, period: str = "historical") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match all series to the benchmark dates and list Cboe-only observations."""
    validate_source(benchmark, "GSPC", benchmark=True)
    validate_source(vix, "VIX")
    parts = []
    for symbol in STOCKS:
        frame = stocks[symbol]
        validate_source(frame, symbol, stock=True)
        if not frame.index.equals(benchmark.index):
            raise ValueError(f"{symbol}: dates differ from the S&P 500 calendar")
        parts.append(frame[STOCK_FIELDS].rename(columns={"Adj Close": "AdjClose", "Stock Splits": "StockSplits"}).add_prefix(f"{symbol}_"))
    missing = benchmark.index.difference(vix.index)
    if len(missing):
        raise ValueError(f"VIX: missing closes on {len(missing)} S&P 500 dates")
    extra = vix.index.difference(benchmark.index)
    excluded = pd.DataFrame([
        {"Date": str(date.date()), "Period": period, "Instrument": "VIX",
         "Reason": "Cboe publication outside the S&P 500 trading calendar"}
        for date in extra
    ], columns=EXCLUSION_FIELDS)
    parts.extend([benchmark[OHLC + ["Adj Close", "Volume", "Dividends", "Stock Splits"]]
                  .rename(columns={"Adj Close": "AdjClose", "Stock Splits": "StockSplits"}).add_prefix("GSPC_"),
                  vix.loc[benchmark.index, OHLC].add_prefix("VIX_")])
    result = pd.concat(parts, axis=1)
    result.index.name = "Date"
    return result, excluded


def assemble_master(aligned: pd.DataFrame, prior_close: pd.Series | None = None) -> pd.DataFrame:
    """Calculate percentage returns, optionally using the last historical close."""
    if prior_close is not None:
        if not isinstance(prior_close.name, pd.Timestamp) or prior_close.name >= aligned.index[0]:
            raise ValueError("The prior close must have a date earlier than the new period")
    result = aligned.copy()
    for symbol in (*STOCKS, "GSPC"):
        close = aligned[f"{symbol}_Close"]
        previous = close.shift(1)
        if prior_close is not None:
            value = float(prior_close[f"{symbol}_Close"])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{symbol}: invalid prior close")
            previous.iloc[0] = value
        result[f"{symbol}_Return"] = 100 * (close / previous - 1)
    for field, values in (("Year", result.index.year), ("Quarter", result.index.quarter), ("Month", result.index.month)):
        result[field] = values.astype("int64")
    for symbol in STOCKS:
        result[f"{symbol}_Volume"] = result[f"{symbol}_Volume"].astype("int64")
    return result[master_columns()]


def _quality(period: str, instrument: str, check: str, count: int, details: str = "") -> dict:
    return dict(zip(QUALITY_FIELDS, [period, instrument, check, "pass", int(count), details]))


def _manifest(root: Path, snapshot: Path) -> tuple[dict, dict]:
    path = snapshot / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError(f"Incomplete acquisition manifest: {path.relative_to(root)}")
    return manifest, {"file": path.relative_to(root).as_posix(), "sha256": sha256(path)}


def _verified_record(root: Path, snapshot: Path, records: list[dict], **match) -> tuple[Path, dict]:
    matches = [record for record in records if all(record.get(key) == value for key, value in match.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected one acquisition record for {match}")
    record = matches[0]
    path = project_path(snapshot, record["file"])
    actual = sha256(path)
    if actual != record["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.relative_to(root)}")
    return path, {"file": path.relative_to(root).as_posix(), "sha256": actual}


def _read_yahoo(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, float_precision="round_trip")
    frame["Date"] = pd.to_datetime(frame["Date"], format="%Y-%m-%d", errors="raise")
    return frame.set_index("Date")


def _load_period(root: Path, config: dict, period: str) -> tuple:
    boundary = config["periods"][period]
    sources = {name: project_path(root, path) for name, path in config["sources"].items()}
    yahoo, yahoo_meta = _manifest(root, sources["yahoo"])
    cboe, cboe_meta = _manifest(root, sources["cboe"])
    inputs = [yahoo_meta, cboe_meta]
    checks = []
    frames = {}
    for symbol in (*STOCKS, "GSPC"):
        path, record = _verified_record(root, sources["yahoo"], yahoo["records"],
                                        period=period, symbol="^GSPC" if symbol == "GSPC" else symbol)
        inputs.append(record)
        frame = _read_yahoo(path)
        validate_source(frame, symbol, stock=symbol in STOCKS, benchmark=symbol == "GSPC")
        if not frame.index.to_series().between(boundary["start"], boundary["end"]).all():
            raise ValueError(f"{period}/{symbol}: observations outside the formal period")
        frames[symbol] = frame
        checks.extend([
            _quality(period, symbol, "input_sha256", 1),
            _quality(period, symbol, "source_schema_dates_prices_ohlc", len(frame)),
        ])
        if symbol in STOCKS:
            checks.append(_quality(period, symbol, "positive_integer_volume_and_valid_actions", len(frame)))
    benchmark = frames.pop("GSPC")
    if (len(benchmark) != boundary["rows"]
            or str(benchmark.index[0].date()) != boundary["first_session"]
            or str(benchmark.index[-1].date()) != boundary["last_session"]):
        raise ValueError(f"{period}: unexpected benchmark row count or date boundaries")
    path, record = _verified_record(root, sources["cboe"], cboe["records"], name="VIX")
    inputs.append(record)
    vix = pd.read_csv(path, float_precision="round_trip")
    vix["Date"] = pd.to_datetime(vix["DATE"], format="%m/%d/%Y", errors="raise")
    vix = vix.set_index("Date")
    # The Cboe file covers 1990 onwards; only this period enters validation or alignment.
    vix = vix.loc[vix.index.to_series().between(boundary["start"], boundary["end"])].rename(columns=str.title)
    aligned, excluded = align_sources(frames, benchmark, vix, period)
    checks.extend([
        _quality(period, "VIX", "input_sha256", 1),
        _quality(period, "VIX", "source_schema_dates_prices_ohlc", len(vix)),
        _quality(period, "all", "exact_stock_calendar_and_expected_coverage", len(aligned), f"{boundary['first_session']} to {boundary['last_session']}"),
        _quality(period, "VIX", "closes_on_every_stock_date", len(aligned)),
        _quality(period, "VIX", "logged_calendar_exclusions", len(excluded)),
    ])
    return aligned, excluded, checks, inputs


def _check_master(master: pd.DataFrame, period: str) -> list[dict]:
    if list(master.columns) != master_columns():
        raise ValueError(f"{period}: incorrect master schema")
    expected_missing = pd.DataFrame(False, index=master.index, columns=master.columns)
    if period == "historical":
        expected_missing.loc[master.index[0], [f"{symbol}_Return" for symbol in (*STOCKS, "GSPC")]] = True
    if not master.isna().equals(expected_missing):
        raise ValueError(f"{period}: unexpected missing values in master")
    valid = master.isna() | (master.gt(-float("inf")) & master.lt(float("inf")))
    if not valid.all().all():
        raise ValueError(f"{period}: non-finite master values")
    integer_fields = ["Year", "Quarter", "Month"] + [f"{symbol}_Volume" for symbol in STOCKS]
    if not all(pd.api.types.is_integer_dtype(master[field]) for field in integer_fields):
        raise ValueError(f"{period}: calendar fields and stock volume must be integers")
    for field, expected in (("Year", master.index.year), ("Quarter", master.index.quarter), ("Month", master.index.month)):
        if not master[field].eq(expected).all():
            raise ValueError(f"{period}: {field} does not match the date")
    return [
        _quality(period, "all", "master_schema", len(master.columns) + 1, "Includes Date"),
        _quality(period, "all", "allowed_missing_returns_only", int(master.isna().sum().sum())),
        _quality(period, "all", "finite_master_values", int(master.notna().sum().sum())),
        _quality(period, "all", "integer_calendar_and_stock_volume", len(master)),
        _quality(period, "all", "first_return_policy", 7,
                 "No preceding historical close" if period == "historical" else "Prior close from final historical date"),
    ]


def _large_moves(master: pd.DataFrame, period: str, threshold: float, notes: dict) -> pd.DataFrame:
    rows = []
    for symbol in (*STOCKS, "GSPC"):
        returns = master[f"{symbol}_Return"]
        for date, value in returns[returns.abs() > threshold].items():
            key = f"{date.date()}/{symbol}"
            if period == "historical":
                if key not in notes:
                    raise ValueError(f"Historical large move needs a source note: {key}")
                note = notes[key]
            else:
                note = {"note": "Flagged only; unseen event not investigated", "source": ""}
            rows.append(dict(zip(MOVE_FIELDS, [str(date.date()), period, symbol, value, note["note"], note["source"]])))
    return pd.DataFrame(rows, columns=MOVE_FIELDS).sort_values(["Date", "Symbol"]).reset_index(drop=True)


def _sample_returns(root: Path, config: dict, masters: dict) -> pd.DataFrame:
    rows = []
    yahoo = project_path(root, config["sources"]["yahoo"])
    for sample in config.get("return_checks", []):
        period, symbol, date = sample["period"], sample["symbol"], sample["date"]
        if period not in masters:
            continue
        # Decimal arithmetic on raw CSV strings is independent of pandas' return calculation.
        with (yahoo / period / f"{symbol}.csv").open(encoding="utf-8", newline="") as handle:
            records = list(csv.DictReader(handle))
        position = next(i for i, row in enumerate(records) if row["Date"] == date)
        current = records[position]
        if position:
            previous = records[position - 1]
        elif period == "unseen":
            with (yahoo / "historical" / f"{symbol}.csv").open(encoding="utf-8", newline="") as handle:
                previous = list(csv.DictReader(handle))[-1]
        else:
            raise ValueError("A hand-check sample cannot be the first historical date")
        expected = float(100 * (Decimal(current["Close"]) - Decimal(previous["Close"])) / Decimal(previous["Close"]))
        actual = float(masters[period].loc[pd.Timestamp(date), f"{symbol}_Return"])
        if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10):
            raise ValueError(f"Independent return check failed: {sample}")
        rows.append(dict(zip(SAMPLE_FIELDS, [period, symbol, date, previous["Date"], previous["Close"], current["Close"], expected, actual, abs(expected - actual)])))
    return pd.DataFrame(rows, columns=SAMPLE_FIELDS)


def _write_csv(frame: pd.DataFrame, path: Path, *, dated: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=dated, index_label="Date" if dated else None,
                 date_format="%Y-%m-%d", lineterminator="\n", encoding="utf-8")


def build_master(config_path: Path, *, historical_only: bool = False) -> dict:
    """Validate the chosen inputs and save masters, checkpoints, and audit tables."""
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if tuple(config["stocks"]) != STOCKS:
        raise ValueError("The master must use the six configured project stocks in their recorded order")
    periods = ["historical"] if historical_only else ["historical", "unseen"]
    historical = config["periods"]["historical"]
    if pd.Timestamp(historical["end"]) >= pd.Timestamp("2026-01-01"):
        raise ValueError("Historical data must end before 2026")
    if not historical_only:
        unseen = config["periods"]["unseen"]
        if (pd.Timestamp(unseen["start"]) <= pd.Timestamp(historical["end"])
                or pd.Timestamp(unseen["start"]) < pd.Timestamp("2026-01-01")
                or pd.Timestamp(unseen["end"]) > pd.Timestamp("2026-07-31")):
            raise ValueError("The unseen period must be separate and inside January-July 2026")
    outputs = {name: project_path(root, relative) for name, relative in config["outputs"].items()}
    if any(path.is_relative_to(root / "data/raw") for path in outputs.values()):
        raise ValueError("Build outputs cannot overwrite raw data")
    notes_path = project_path(root, config["large_move_notes"]) if "large_move_notes" in config else None
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path else {}
    threshold = float(config["large_move_threshold_percent"])
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("The large-move threshold must be finite and positive")
    masters, checkpoints, exclusions, moves, checks, inputs = {}, {}, [], [], [], []
    for period in periods:
        aligned, excluded, period_checks, period_inputs = _load_period(root, config, period)
        prior = checkpoints["historical"].iloc[-1] if period == "unseen" else None
        master = assemble_master(aligned, prior_close=prior)
        checks.extend(period_checks + _check_master(master, period))
        large_moves = _large_moves(master, period, threshold, notes)
        checks.append(_quality(period, "all", "large_moves_flagged_without_changes", len(large_moves)))
        masters[period], checkpoints[period] = master, aligned
        exclusions.append(excluded)
        moves.append(large_moves)
        inputs.extend(period_inputs)
    samples = _sample_returns(root, config, masters)
    for period in periods:
        checks.append(_quality(period, "all", "independent_decimal_return_checks", int(samples["Period"].eq(period).sum())))
    saved = []
    for period in periods:
        for frame, path in ((checkpoints[period], outputs["interim"] / f"aligned_{period}.csv"),
                            (masters[period], outputs["processed"] / f"master_{period}.csv")):
            _write_csv(frame, path, dated=True)
            saved.append(path)
    tables = [
        (pd.concat(exclusions, ignore_index=True), outputs["interim"] / "excluded_rows.csv"),
        (pd.DataFrame(checks, columns=QUALITY_FIELDS), outputs["metrics"] / "phase1_quality_summary.csv"),
        (pd.concat(moves, ignore_index=True), outputs["metrics"] / "phase1_large_moves.csv"),
        (samples, outputs["metrics"] / "phase1_return_checks.csv"),
    ]
    for frame, path in tables:
        _write_csv(frame, path)
        saved.append(path)
    dependencies = []
    for path in (config_path, notes_path, root / "pyproject.toml", root / "uv.lock"):
        if path is not None and path.is_file() and path.is_relative_to(root):
            dependencies.append({"file": path.relative_to(root).as_posix(), "sha256": sha256(path)})
    # Docker installs the package outside the project, so the module is named by its
    # package path; otherwise a non-editable install would leave it out of the manifest.
    module = Path(__file__).resolve()
    dependencies.append({"file": module.relative_to(module.parents[2]).as_posix(), "sha256": sha256(module)})
    manifest = {
        "status": "complete", "periods": periods, "settings": config,
        "versions": {"python": platform.python_version(), "pandas": pd.__version__},
        "price_policy": "Yahoo split-adjusted Close; no dividends; AdjClose is reference only",
        "calendar": "Yahoo S&P 500 dates; exact stock match; Cboe VIX required on every date",
        "return_units": "percent", "csv_line_endings": "LF",
        "hash_scope": "Only selected Yahoo instruments and periods; shared Cboe file is hashed in full and sliced before price validation",
        "inputs": sorted({entry["file"]: entry for entry in inputs}.values(), key=lambda entry: entry["file"]),
        "build_files": dependencies,
        "datasets": {period: {"rows": len(frame), "columns_including_date": len(frame.columns) + 1,
                               "first_date": str(frame.index[0].date()), "last_date": str(frame.index[-1].date()),
                               "missing_values": int(frame.isna().sum().sum())} for period, frame in masters.items()},
        "outputs": {path.relative_to(root).as_posix(): sha256(path) for path in saved},
    }
    manifest_path = outputs["processed"] / "master_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/master_data.json"))
    parser.add_argument("--historical-only", action="store_true",
                        help="Build without opening any Yahoo unseen files; manifest lists only this run's outputs")
    args = parser.parse_args()
    manifest = build_master(args.config, historical_only=args.historical_only)
    for period, dataset in manifest["datasets"].items():
        print(f"{period}: {dataset['rows']} rows, {dataset['columns_including_date']} columns, "
              f"{dataset['first_date']} to {dataset['last_date']}")
    print("Manifest: " + manifest["settings"]["outputs"]["processed"] + "/master_manifest.json")


if __name__ == "__main__":
    main()
