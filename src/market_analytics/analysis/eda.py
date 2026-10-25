"""Phase 2 exploratory summaries, calculated from the historical master only."""

import argparse
import itertools
import json
import math
import platform
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import statsmodels
import statsmodels.api as sm

from market_analytics.data.master import STOCKS, project_path, sha256


UNSEEN_START = pd.Timestamp("2026-01-01")
OK = "ok"
INSUFFICIENT = "insufficient_observations"
ZERO_VARIANCE = "zero_variance"
INCOMPLETE = "incomplete_window"
# Running-sum rolling correlations and independent recalculations agree far
# more closely than this; a larger gap means a calculation error.
CHECK_TOLERANCE = 1e-9


def load_config(config_path: Path) -> tuple[Path, dict]:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if tuple(config["stocks"]) != STOCKS:
        raise ValueError("EDA must use the six project stocks in their recorded order")
    if pd.Timestamp(config["period"]["end"]) >= UNSEEN_START:
        raise ValueError("The EDA period must end before 2026")
    if "unseen" in Path(config["input"]).name:
        raise ValueError("EDA reads the historical master only")
    return root, config


def instruments(config: dict) -> list[str]:
    return list(config["stocks"]) + [config["benchmark"]]


def required_columns(config: dict) -> list[str]:
    return ([f"{symbol}_{field}" for symbol in instruments(config) for field in ("Close", "Return")]
            + ["VIX_Close"])


def read_input(root: Path, config: dict) -> tuple[pd.DataFrame, str]:
    """Read the historical master after confirming it is the file the Phase 1 build recorded."""
    path = project_path(root, config["input"])
    manifest = json.loads(project_path(root, config["manifest"]).read_text(encoding="utf-8"))
    expected = manifest["outputs"].get(config["input"])
    if expected is None:
        raise ValueError(f"{config['input']} is not listed in the build manifest")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{config['input']} does not match its manifest hash")
    frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    missing = sorted(set(required_columns(config)) - set(frame.columns))
    if missing:
        raise ValueError(f"Historical master is missing columns {missing}")
    return frame[required_columns(config)], actual


def check(name: str, count: int, details: str = "") -> dict:
    return {"check": name, "status": "pass", "count": int(count), "details": details}


def validate_input(frame: pd.DataFrame, config: dict) -> list[dict]:
    """Stop on anything unexpected rather than filling or dropping it."""
    period = config["period"]
    missing = sorted(set(required_columns(config)) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing columns {missing}")
    dates = frame.index
    if (not isinstance(dates, pd.DatetimeIndex) or dates.has_duplicates
            or not dates.is_monotonic_increasing or not dates.equals(dates.normalize())):
        raise ValueError("Dates must be unique, increasing daily dates")
    if dates[0] < pd.Timestamp(period["start"]) or dates[-1] > pd.Timestamp(period["end"]):
        raise ValueError("Input contains dates outside the historical period")
    if dates[-1] >= UNSEEN_START:
        raise ValueError("Input contains unseen-period dates")
    if (len(frame) != period["rows"] or dates[0] != pd.Timestamp(period["first_session"])
            or dates[-1] != pd.Timestamp(period["last_session"])):
        raise ValueError("Input coverage differs from the recorded historical sessions")
    closes = frame[[f"{symbol}_Close" for symbol in instruments(config)] + ["VIX_Close"]]
    if not (np.isfinite(closes.to_numpy()).all() and (closes.to_numpy() > 0).all()):
        raise ValueError("Every Close, including VIX, must be finite and positive")
    returns = frame[[f"{symbol}_Return" for symbol in instruments(config)]]
    if not returns.iloc[0].isna().all():
        raise ValueError("The first historical returns must be missing")
    if not np.isfinite(returns.iloc[1:].to_numpy()).all():
        raise ValueError("Unexpected missing or non-finite return after the first date")
    return [
        check("required_columns", len(required_columns(config))),
        check("unique_increasing_dates_in_period", len(frame),
              f"{dates[0].date()} to {dates[-1].date()}"),
        check("positive_finite_closes_including_vix", closes.size),
        check("missing_returns_only_on_first_date", int(returns.isna().sum().sum()),
              str(dates[0].date())),
    ]


def split_input(frame: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Return Closes on every date, returns from the second date, and VIX."""
    names = instruments(config)
    closes = frame[[f"{symbol}_Close" for symbol in names]].set_axis(names, axis=1)
    returns = frame[[f"{symbol}_Return" for symbol in names]].set_axis(names, axis=1).iloc[1:]
    return closes, returns, frame["VIX_Close"]


def day(value) -> str | None:
    return None if value is None else str(pd.Timestamp(value).date())


def compounded_pct(returns: pd.Series) -> float:
    return float(100 * (np.prod(1 + returns.to_numpy() / 100) - 1))


def drawdown_series(returns: pd.Series, base_date: pd.Timestamp) -> pd.Series:
    """Percent below the running peak of a wealth path that starts at 1 on base_date."""
    wealth = pd.concat([pd.Series([1.0], index=[base_date]), (1 + returns / 100).cumprod()])
    return 100 * (wealth / wealth.cummax() - 1)


def max_drawdown(returns: pd.Series, base_date: pd.Timestamp) -> tuple[float, str | None, str | None]:
    drawdown = drawdown_series(returns, base_date)
    if drawdown.min() == 0:
        return 0.0, None, None
    trough = drawdown.idxmin()
    wealth = pd.concat([pd.Series([1.0], index=[base_date]), (1 + returns / 100).cumprod()])
    return float(drawdown.min()), day(wealth.loc[:trough].idxmax()), day(trough)


def summary_row(returns: pd.Series, base_date: pd.Timestamp, config: dict) -> dict:
    n = len(returns)
    row = {"n": n, "first_date": day(returns.index[0]) if n else None,
           "last_date": day(returns.index[-1]) if n else None, "base_date": day(base_date)}
    if n < config["min_observations"]:
        return row | {"status": INSUFFICIENT}
    std = float(returns.std(ddof=1))
    peak_loss, peak_date, trough_date = max_drawdown(returns, base_date)
    return row | {
        "mean_pct": float(returns.mean()), "median_pct": float(returns.median()),
        "min_pct": float(returns.min()), "max_pct": float(returns.max()), "std_pct": std,
        "annualized_vol_pct": std * math.sqrt(config["annualization_days"]),
        "compounded_return_pct": compounded_pct(returns), "max_drawdown_pct": peak_loss,
        "drawdown_peak_date": peak_date, "drawdown_trough_date": trough_date, "status": OK,
    }


SUMMARY_FIELDS = ["n", "first_date", "last_date", "base_date", "mean_pct", "median_pct", "min_pct",
                  "max_pct", "std_pct", "annualized_vol_pct", "compounded_return_pct",
                  "max_drawdown_pct", "drawdown_peak_date", "drawdown_trough_date", "status"]


def return_summaries(closes: pd.DataFrame, returns: pd.DataFrame,
                     config: dict) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Whole-period and calendar-year summaries, each checked against its Close ratio."""
    whole, annual, ratio_checks = [], [], 0
    for symbol in instruments(config):
        windows = [("2018-2025", returns[symbol], closes.index[0])]
        for year in sorted(set(returns.index.year)):
            selected = returns.loc[returns.index.year == year, symbol]
            # Each year starts from the preceding session's Close; 2018 starts from 2018-01-02.
            windows.append((str(year), selected, closes.index[closes.index < selected.index[0]][-1]))
        for label, selected, base in windows:
            row = summary_row(selected, base, config)
            if row["status"] == OK:
                ratio = 100 * (closes.loc[selected.index[-1], symbol] / closes.loc[base, symbol] - 1)
                if not math.isclose(row["compounded_return_pct"], ratio, rel_tol=1e-9, abs_tol=1e-9):
                    raise ValueError(f"{symbol} {label}: compounded return differs from the Close ratio")
                ratio_checks += 1
            (whole if label == "2018-2025" else annual).append(
                {"instrument": symbol} | ({} if label == "2018-2025" else {"year": int(label)}) | row)
    whole = pd.DataFrame(whole).reindex(columns=["instrument"] + SUMMARY_FIELDS)
    annual = pd.DataFrame(annual).reindex(columns=["instrument", "year"] + SUMMARY_FIELDS)
    return whole, annual, [check("compounded_return_matches_close_ratio", ratio_checks)]


def stock_pairs(stocks) -> list[tuple[str, str]]:
    """The 15 unordered pairs, in the fixed display order (MSFT_GOOGL first)."""
    return list(itertools.combinations(stocks, 2))


def is_constant(values: pd.Series) -> bool:
    # Equality is exact; a standard deviation of identical floats can come out as
    # a tiny positive number because the mean is rounded.
    return bool(values.max() == values.min())


def correlation(x: pd.Series, y: pd.Series, min_observations: int) -> tuple[float, str]:
    if len(x) < min_observations:
        return math.nan, INSUFFICIENT
    if is_constant(x) or is_constant(y):
        return math.nan, ZERO_VARIANCE
    return float(np.corrcoef(x.to_numpy(), y.to_numpy())[0, 1]), OK


def correlation_fields(prefix: str, x: pd.Series, y: pd.Series, config: dict) -> dict:
    value, status = correlation(x, y, config["min_observations"])
    return {f"{prefix}correlation": value, f"{prefix}n": len(x),
            f"{prefix}first_date": day(x.index[0]) if len(x) else None,
            f"{prefix}last_date": day(x.index[-1]) if len(x) else None, f"{prefix}status": status}


def pair_correlations(closes: pd.DataFrame, returns: pd.DataFrame, config: dict) -> pd.DataFrame:
    log_prices = np.log(closes[config["stocks"]])
    rows = []
    for a, b in stock_pairs(config["stocks"]):
        rows.append({"pair": f"{a}_{b}", "stock_a": a, "stock_b": b}
                    | correlation_fields("return_", returns[a], returns[b], config)
                    | correlation_fields("log_price_", log_prices[a], log_prices[b], config))
    return pd.DataFrame(rows)


def correlation_matrix(pairs: pd.DataFrame, returns: pd.DataFrame, config: dict) -> pd.DataFrame:
    stocks = config["stocks"]
    matrix = pd.DataFrame(np.eye(len(stocks)), index=stocks, columns=stocks)
    for stock in stocks:
        if len(returns) < config["min_observations"] or is_constant(returns[stock]):
            matrix.loc[stock, stock] = math.nan
    for row in pairs.itertuples():
        matrix.loc[row.stock_a, row.stock_b] = matrix.loc[row.stock_b, row.stock_a] = row.return_correlation
    matrix.index.name = "symbol"
    return matrix


def regression(y: pd.Series, x: pd.Series, config: dict) -> dict:
    """OLS of stock on benchmark returns with an explicit intercept."""
    row = {"n": len(y), "first_date": day(y.index[0]) if len(y) else None,
           "last_date": day(y.index[-1]) if len(y) else None}
    if len(y) < config["min_observations"]:
        return row | {"status": INSUFFICIENT}
    if is_constant(x) or is_constant(y):
        # Constant x makes the design rank-deficient; constant y makes R-squared
        # undefined. The adopted policy omits both fits.
        return row | {"status": ZERO_VARIANCE}
    # has_constant="add": the default skips the intercept if a column already looks constant.
    fit = sm.OLS(y.to_numpy(), sm.add_constant(x.to_numpy(), has_constant="add")).fit()
    alpha, beta = (float(value) for value in fit.params)
    corr = float(np.corrcoef(y.to_numpy(), x.to_numpy())[0, 1])
    direct_beta = float(np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1))
    if (not math.isclose(beta, direct_beta, rel_tol=CHECK_TOLERANCE, abs_tol=CHECK_TOLERANCE)
            or not math.isclose(fit.rsquared, corr ** 2, rel_tol=0, abs_tol=CHECK_TOLERANCE)):
        raise ValueError("Regression does not match the covariance identities")
    return row | {"alpha_pct": alpha, "beta": beta, "r_squared": float(fit.rsquared),
                  "correlation": corr, "status": OK}


def benchmark_sensitivity(returns: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
    benchmark, rows = config["benchmark"], []
    periods = [("2018-2025", returns)] + [(str(year), returns[returns.index.year == year])
                                         for year in sorted(set(returns.index.year))]
    for stock in config["stocks"]:
        for label, selected in periods:
            rows.append({"stock": stock, "period": label}
                        | regression(selected[stock], selected[benchmark], config))
    table = pd.DataFrame(rows).reindex(columns=[
        "stock", "period", "alpha_pct", "beta", "r_squared", "correlation",
        "n", "first_date", "last_date", "status"])
    fitted = int(table["status"].eq(OK).sum())
    return table, [check("beta_and_r_squared_match_covariance_identities", fitted)]


def annual_pair_correlations(returns: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for a, b in stock_pairs(config["stocks"]):
        for year in sorted(set(returns.index.year)):
            selected = returns[returns.index.year == year]
            rows.append({"pair": f"{a}_{b}", "stock_a": a, "stock_b": b, "year": year}
                        | correlation_fields("", selected[a], selected[b], config))
    return pd.DataFrame(rows)


def rolling_correlations(returns: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
    """Trailing windows ending on each return date, including that day's return."""
    window, frames, largest_gap, spot_checks = config["rolling_window"], [], 0.0, 0
    for a, b in stock_pairs(config["stocks"]):
        x, y = returns[a], returns[b]
        value = x.rolling(window, min_periods=window).corr(y)
        count = (x.notna() & y.notna()).astype(int).rolling(window, min_periods=1).sum().astype(int)
        constant = ((x.rolling(window).max() == x.rolling(window).min())
                    | (y.rolling(window).max() == y.rolling(window).min()))
        # pandas returns inf for a constant window, so status comes from the inputs.
        status = np.where(count < window, INCOMPLETE, np.where(constant, ZERO_VARIANCE, OK))
        frame = pd.DataFrame({"date": [day(d) for d in x.index], "pair": f"{a}_{b}", "n": count.to_numpy(),
                              "correlation": value.where(status == OK).to_numpy(), "status": status})
        defined = frame.loc[frame["status"].eq(OK), "correlation"]
        if not (np.isfinite(defined).all() and defined.abs().le(1 + CHECK_TOLERANCE).all()):
            raise ValueError(f"{a}_{b}: rolling correlation outside [-1, 1]")
        positions = np.flatnonzero(status == OK)
        for position in positions[[0, len(positions) // 2, -1]] if len(positions) else []:
            direct = np.corrcoef(x.iloc[position - window + 1:position + 1],
                                 y.iloc[position - window + 1:position + 1])[0, 1]
            largest_gap = max(largest_gap, abs(direct - value.iloc[position]))
            spot_checks += 1
        frames.append(frame)
    if largest_gap > CHECK_TOLERANCE:
        raise ValueError(f"Rolling correlation differs from a direct calculation by {largest_gap}")
    return pd.concat(frames, ignore_index=True), [
        check("rolling_matches_direct_window_calculation", spot_checks, f"largest gap {largest_gap:.3e}")]


def vix_boundaries(vix: pd.Series, dates: pd.DatetimeIndex, config: dict) -> dict:
    """Quantile boundaries estimated on the return dates only."""
    groups = len(config["vix_groups"])
    levels = [index / groups for index in range(1, groups)]
    sample = vix.loc[dates]
    values = np.quantile(sample.to_numpy(), levels, method=config["vix_quantile_method"])
    return {"levels": levels, "method": config["vix_quantile_method"],
            "boundaries": [float(value) for value in values], "labels": list(config["vix_groups"]),
            "estimation_n": len(sample), "estimation_first_date": day(sample.index[0]),
            "estimation_last_date": day(sample.index[-1])}


def assign_vix_groups(vix: pd.Series, boundaries: dict) -> pd.Series:
    # side="left": a value equal to a boundary goes to the lower group, as the rule requires.
    positions = np.searchsorted(np.asarray(boundaries["boundaries"]), vix.to_numpy(), side="left")
    return pd.Series(np.asarray(boundaries["labels"])[positions], index=vix.index, name="vix_group")


def vix_tables(returns: pd.DataFrame, groups: pd.Series, config: dict) -> tuple[pd.DataFrame, ...]:
    labels, stock_rows, pair_rows, year_rows = config["vix_groups"], [], [], []
    years = sorted(set(returns.index.year))
    for label in labels:
        selected = returns[groups.loc[returns.index].eq(label).to_numpy()]
        dates = {"n": len(selected), "first_date": day(selected.index[0]) if len(selected) else None,
                 "last_date": day(selected.index[-1]) if len(selected) else None}
        for symbol in instruments(config):
            enough = len(selected) >= config["min_observations"]
            stock_rows.append({"vix_group": label, "instrument": symbol} | dates | {
                "std_pct": float(selected[symbol].std(ddof=1)) if enough else math.nan,
                "mean_abs_pct": float(selected[symbol].abs().mean()) if enough else math.nan,
                "status": OK if enough else INSUFFICIENT})
        for a, b in stock_pairs(config["stocks"]):
            pair_rows.append({"vix_group": label, "pair": f"{a}_{b}", "stock_a": a, "stock_b": b}
                             | correlation_fields("", selected[a], selected[b], config))
        for year in years:
            year_rows.append({"vix_group": label, "year": year,
                              "n": int((selected.index.year == year).sum())})
    return pd.DataFrame(stock_rows), pd.DataFrame(pair_rows), pd.DataFrame(year_rows)


def write_csv(frame: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=index, lineterminator="\n", encoding="utf-8")


def count_checks(tables: dict, config: dict, return_dates: int, years: int) -> list[dict]:
    """Row counts implied by the inputs; on the real master these are 7, 56, 15, and so on."""
    n_instruments, n_stocks = len(instruments(config)), len(config["stocks"])
    n_pairs, groups = math.comb(n_stocks, 2), len(config["vix_groups"])
    expected = {
        "stock_summary": n_instruments, "stock_annual_summary": n_instruments * years,
        "pair_correlations": n_pairs, "benchmark_sensitivity": n_stocks * (1 + years),
        "pair_annual_correlations": n_pairs * years, "rolling_correlations": return_dates * n_pairs,
        "vix_group_stock_summary": groups * n_instruments, "vix_group_pair_correlations": groups * n_pairs,
        "vix_group_year_counts": groups * years,
    }
    for name, rows in expected.items():
        if len(tables[name]) != rows:
            raise ValueError(f"{name}: expected {rows} rows, found {len(tables[name])}")
    incomplete = int(tables["rolling_correlations"]["status"].eq(INCOMPLETE).sum())
    if incomplete != min(return_dates, config["rolling_window"] - 1) * n_pairs:
        raise ValueError("Unexpected number of incomplete rolling windows")
    if tables["vix_group_year_counts"]["n"].sum() != return_dates:
        raise ValueError("VIX group counts do not reconcile to the return dates")
    pairs = tables["pair_correlations"]
    if (pairs["pair"].nunique() != n_pairs
            or (pairs["stock_a"] == pairs["stock_b"]).any()):
        raise ValueError("Pair list has duplicates or self-pairs")
    matrix = tables["return_correlation_matrix"].to_numpy()
    if not np.array_equal(matrix, matrix.T, equal_nan=True):
        raise ValueError("Correlation matrix is not symmetric")
    correlations = pd.concat([
        pairs["return_correlation"], pairs["log_price_correlation"],
        tables["pair_annual_correlations"]["correlation"], tables["benchmark_sensitivity"]["correlation"],
        tables["vix_group_pair_correlations"]["correlation"], tables["rolling_correlations"]["correlation"],
    ]).dropna()
    if not correlations.abs().le(1 + CHECK_TOLERANCE).all():
        raise ValueError("A correlation lies outside [-1, 1]")
    return [check(f"{name}_rows", rows) for name, rows in expected.items()] + [
        check("incomplete_rolling_windows", incomplete),
        check("vix_group_counts_reconcile_to_return_dates", return_dates),
        check("unique_unordered_pairs_and_symmetric_matrix", n_pairs),
        check("defined_correlations_within_bounds", len(correlations)),
    ]


def analyse(frame: pd.DataFrame, config: dict) -> tuple[dict, dict, list[dict]]:
    """Every table, the VIX grouping, and the checks, without reading or writing files."""
    checks = validate_input(frame, config)
    closes, returns, vix = split_input(frame, config)
    whole, annual, summary_checks = return_summaries(closes, returns, config)
    pairs = pair_correlations(closes, returns, config)
    benchmark, benchmark_checks = benchmark_sensitivity(returns, config)
    rolling, rolling_checks = rolling_correlations(returns, config)
    boundaries = vix_boundaries(vix, returns.index, config)
    groups = assign_vix_groups(vix.loc[returns.index], boundaries)
    saved = json.loads(json.dumps(boundaries))
    if not assign_vix_groups(vix.loc[returns.index], saved).equals(groups):
        raise ValueError("Saved VIX boundaries do not reproduce the group assignments")
    vix_stock, vix_pairs, vix_years = vix_tables(returns, groups, config)
    tables = {
        "stock_summary": whole, "stock_annual_summary": annual, "pair_correlations": pairs,
        "return_correlation_matrix": correlation_matrix(pairs, returns, config),
        "benchmark_sensitivity": benchmark, "pair_annual_correlations": annual_pair_correlations(returns, config),
        "rolling_correlations": rolling, "vix_group_stock_summary": vix_stock,
        "vix_group_pair_correlations": vix_pairs, "vix_group_year_counts": vix_years,
    }
    checks += summary_checks + benchmark_checks + rolling_checks
    checks.append(check("saved_vix_boundaries_reproduce_groups", len(groups)))
    checks += count_checks(tables, config, len(returns), len(set(returns.index.year)))
    return tables, boundaries, checks


def run_eda(config_path: Path, *, figures: bool = True) -> dict:
    """Run the analysis on the configured historical master and save tables, figures, and metadata."""
    from market_analytics.analysis import eda_plots

    config_path = config_path.resolve()
    root, config = load_config(config_path)
    frame, input_hash = read_input(root, config)
    tables, boundaries, checks = analyse(frame, config)
    metrics = project_path(root, config["outputs"]["metrics"])
    saved = []
    for name, table in tables.items():
        path = metrics / f"{name}.csv"
        write_csv(table, path, index=name == "return_correlation_matrix")
        saved.append(path)
    figure_paths = []
    if figures:
        figure_paths = eda_plots.save_figures(frame, tables, boundaries, config,
                                              project_path(root, config["outputs"]["figures"]))
    if sha256(project_path(root, config["input"])) != input_hash:
        raise ValueError("The historical master changed during the run")
    checks.append(check("input_unchanged_after_run", 1))
    modules = [Path(__file__).resolve(), Path(eda_plots.__file__).resolve()]
    returns = frame.index[1:]
    metadata = {
        "status": "complete",
        "input": {"file": config["input"], "sha256": input_hash, "manifest": config["manifest"],
                  "rows": len(frame), "first_date": day(frame.index[0]), "last_date": day(frame.index[-1]),
                  "return_dates": len(returns), "first_return_date": day(returns[0])},
        "settings": {"file": config_path.relative_to(root).as_posix(), "sha256": sha256(config_path),
                     "values": config},
        "code": [{"file": path.relative_to(path.parents[2]).as_posix(), "sha256": sha256(path)}
                 for path in modules],
        "conventions": {
            "returns": "Close-based daily percentage returns from the master; dividends excluded",
            "first_return": "2018-01-02 has no return and is excluded, not treated as zero",
            "volatility": "sample standard deviation (ddof=1) of daily percent returns; annualized by sqrt(annualization_days)",
            "compounding": "100 * (product(1 + r/100) - 1); annual windows start from the previous session's Close",
            "drawdown": "wealth starts at 1 on base_date and the start counts toward the running peak",
            "correlation": "Pearson, same-date observations; log-price correlation uses natural log of Close",
            "benchmark": "OLS stock_return = alpha + beta * GSPC_return with explicit intercept; descriptive only",
            "rolling": "trailing window of rolling_window paired returns ending on the labelled date",
            "vix_groups": "linear quantiles of VIX_Close on return dates; value equal to a boundary joins the lower group",
        },
        "vix_groups": boundaries,
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                     "statsmodels": statsmodels.__version__, "matplotlib": matplotlib.__version__},
        "validation": checks,
        "outputs": {path.relative_to(root).as_posix(): sha256(path) for path in saved},
        "figures": [path.relative_to(root).as_posix() for path in figure_paths],
    }
    metadata_path = metrics / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/eda.json"))
    parser.add_argument("--no-figures", action="store_true", help="Save tables and metadata only")
    args = parser.parse_args()
    matplotlib.use("Agg")
    metadata = run_eda(args.config, figures=not args.no_figures)
    print(f"Input: {metadata['input']['file']} ({metadata['input']['rows']} rows, "
          f"{metadata['input']['first_date']} to {metadata['input']['last_date']})")
    print(f"{len(metadata['validation'])} checks passed; {len(metadata['outputs'])} tables and "
          f"{len(metadata['figures'])} figures saved")
    print("Metadata: " + metadata["settings"]["values"]["outputs"]["metrics"] + "/run_metadata.json")


if __name__ == "__main__":
    main()
