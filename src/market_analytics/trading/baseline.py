"""Load the historical handoff and run the fixed statistical baseline."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from market_analytics.data.master import project_path, sha256
from market_analytics.cointegration.selection import write_json
from market_analytics.trading.backtest import simulate


def load_config(path):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if (cfg["normalization"] != {"start": "2025-01-01", "end": "2025-12-31", "ddof": 1}
            or cfg["rules"] != {"entry_threshold": 2., "exit_threshold": 0.,
                "entry_policy": "crossing_while_flat", "initial_state": "flat_no_pending_order",
                "unseen_context": "last_historical_z_only", "execution": "next_session_open",
                "exit_priority": True, "reversal": False, "stop_loss": None, "maximum_holding_sessions": None}
            or cfg["accounting"]["initial_capital"] != 10000.
            or cfg["accounting"]["cost_rate"] != .0005
            or cfg["accounting"]["end_policy"] != "mark_open_at_final_close"):
        raise ValueError("Config differs from the implemented adopted Phase 4 rules")
    return path.parent.parent, cfg


def validate_prices(frame, period):
    dates = frame.index
    if (not isinstance(dates, pd.DatetimeIndex) or frame.empty or dates.hasnans or dates.has_duplicates
            or not dates.is_monotonic_increasing or dates.tz is not None
            or not dates.equals(dates.normalize())):
        raise ValueError("Prices need unique increasing daily dates")
    if (len(frame) != period["rows"] or str(dates[0].date()) != period["first_session"]
            or str(dates[-1].date()) != period["last_session"] or dates[0] < pd.Timestamp(period["start"])
            or dates[-1] > pd.Timestamp(period["end"])):
        raise ValueError("Price sessions differ from the recorded period")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Open and Close prices must be positive and finite")


def _read_prices(root, cfg, period, hashes):
    relative = cfg[period]
    path = project_path(root, relative)
    manifest = json.loads(project_path(root, cfg["manifest"]).read_text(encoding="utf-8"))
    actual = sha256(path)
    if actual != manifest["outputs"].get(relative):
        raise ValueError(f"{period} master does not match its manifest hash; build that period first")
    symbols = sorted({p[k] for p in cfg["pairs"] for k in ("dependent", "independent")})
    columns = [f"{symbol}_{field}" for symbol in symbols for field in ("Open", "Close")]
    frame = pd.read_csv(path, usecols=["Date"] + columns, parse_dates=["Date"]).set_index("Date")
    validate_prices(frame, cfg["periods"][period])
    hashes[relative] = actual
    return frame


def spread_from_prices(frame, parameters):
    return (np.log(frame[parameters["dependent"] + "_Close"]) - parameters["intercept"]
            - parameters["beta"] * np.log(frame[parameters["independent"] + "_Close"]))


def read_handoff(root, cfg):
    """Validate only historical inputs and return their coefficients and hashes."""
    hashes = {}
    frame = _read_prices(root, cfg, "historical", hashes)
    meta_path = project_path(root, cfg["phase3_metadata"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    hashes[cfg["phase3_metadata"]] = sha256(meta_path)
    if meta["input"]["sha256"] != hashes[cfg["historical"]]:
        raise ValueError("Phase 3 used a different historical master")
    def checked_file(relative):
        path = project_path(root, relative)
        actual = sha256(path)
        if actual != meta["outputs"].get(relative):
            raise ValueError(f"Phase 3 output hash mismatch: {relative}")
        hashes[relative] = actual
        return path
    shortlist = pd.read_csv(checked_file(cfg["shortlist"]))
    if shortlist["pair_id"].tolist() != [p["pair_id"] for p in cfg["pairs"]]:
        raise ValueError("Shortlist membership or order differs")
    spreads = pd.read_csv(checked_file(cfg["historical_spreads"]), parse_dates=["Date"]).set_index("Date")
    if not spreads.index.equals(frame.index):
        raise ValueError("Historical spread sessions differ from master sessions")
    parameters = []
    for pair in cfg["pairs"]:
        relative = f"{cfg['ols_directory']}/{pair['pair_id']}/ols_20180102_20251231.json"
        p = json.loads(checked_file(relative).read_text(encoding="utf-8"))
        selected = shortlist.loc[shortlist["pair_id"].eq(pair["pair_id"])].iloc[0]
        if (any(p[k] != pair[k] or selected[k] != pair[k] for k in pair)
                or p["model_version"] != "phase3_v1" or p["shortlisted"] is not True
                or p["fit_start"] != "2018-01-02" or p["fit_end"] != "2025-12-31" or p["nobs"] != 2011
                or p["input_sha256"] != hashes[cfg["historical"]]
                or p["settings_sha256"] != meta["settings"]["sha256"]
                or p["transformation"] != "natural log of Yahoo Close; dividends excluded"
                or p["spread_formula"] != "log(dependent_Close) - intercept - beta * log(independent_Close)"
                or not np.isfinite([p["intercept"], p["beta"]]).all() or p["beta"] <= 0):
            raise ValueError("Incompatible Phase 3 coefficient artifact or direction")
        reconstructed = spread_from_prices(frame, p)
        if not np.allclose(reconstructed, spreads[p["spread_column"]], **cfg["tolerance"]):
            raise ValueError("Historical spread reconstruction differs")
        p = {**p, "ols_path": relative, "ols_sha256": hashes[relative]}
        parameters.append(p)
    return {"prices": frame, "parameters": parameters, "hashes": hashes}


def fit_normalization(residuals):
    dates = residuals.index
    if (len(residuals) < 2 or not isinstance(dates, pd.DatetimeIndex) or dates.hasnans
            or dates.has_duplicates or not dates.is_monotonic_increasing
            or not (dates.year == 2025).all() or not np.isfinite(residuals).all()):
        raise ValueError("Normalization needs finite residuals from 2025 only")
    mean, std = float(residuals.mean()), float(residuals.std(ddof=1))
    if not np.isfinite([mean, std]).all() or std <= 0:
        raise ValueError("Normalization standard deviation must be positive and finite")
    return {"mean": mean, "std": std, "ddof": 1, "fit_start": str(dates[0].date()),
            "fit_end": str(dates[-1].date()), "nobs": len(residuals)}


def apply_normalization(residuals, parameters):
    if (parameters["ddof"] != 1 or not np.isfinite([parameters["mean"], parameters["std"]]).all()
            or parameters["std"] <= 0 or not np.isfinite(residuals).all()):
        raise ValueError("Invalid residuals or normalization artifact")
    return (residuals - parameters["mean"]) / parameters["std"]


def spread_diagnostics(z, signals):
    """Describe band persistence and keep unresolved entry excursions visible."""
    events = []
    for i, row in signals.iterrows():
        for side in ("long", "short"):
            if not row[f"eligible_{side}"]:
                continue
            future = z.iloc[i + 1:]
            hits = future >= 0 if side == "long" else future <= 0
            resolved = bool(hits.any())
            endpoint = hits.index[np.flatnonzero(hits.to_numpy())[0]] if resolved else z.index[-1]
            duration = int(z.index.get_loc(endpoint)) - i
            events.append({"signal_date": row["Date"], "direction": side,
                           "zero_date": str(endpoint.date()) if resolved else "",
                           "observation_end": str(endpoint.date()), "sessions_observed": duration,
                           "status": "reverted" if resolved else "right_censored"})
    diagnostics = {"sessions": len(z), "min_z": z.min(), "max_z": z.max(), "mean_z": z.mean()}
    for side, mask in (("long", z < -2), ("short", z > 2)):
        longest = current = 0
        for outside in mask:
            current = current + 1 if outside else 0
            longest = max(longest, current)
        diagnostics.update({f"{side}_outside_days": int(mask.sum()),
                            f"{side}_outside_proportion": float(mask.mean()),
                            f"{side}_longest_outside_run": longest})
    columns = ["signal_date", "direction", "zero_date", "observation_end", "sessions_observed", "status"]
    return diagnostics, pd.DataFrame(events, columns=columns)


def _annotate(table, p, period, version):
    result = table.copy()
    for key in ("pair_id", "dependent", "independent", "spread_column", "evidence_label"):
        result[key] = p[key]
    result["period"], result["model_version"] = period, version
    result["evaluation_label"] = "in_sample" if period == "historical" else "unseen_fixed_parameters"
    return result


def _save_csv(root, relative, table, outputs):
    path = project_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, float_format="%.17g", lineterminator="\n")
    outputs[relative] = sha256(path)


def run_statistical_baseline(config_path, *, historical_only=False, figures=True):
    from market_analytics.trading import plots

    config_path = Path(config_path).resolve()
    root, cfg = load_config(config_path)
    handoff = read_handoff(root, cfg)
    code_files = [Path(__file__), Path(plots.__file__), Path(__file__).with_name("signals.py"),
                  Path(__file__).with_name("backtest.py"), root / "scripts/run_statistical_baseline.py"]
    code_hashes = {("src/market_analytics/trading/" + p.name if p.parent.name == "trading"
                    else "scripts/" + p.name): sha256(p) for p in code_files}
    versions = {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "matplotlib": matplotlib.__version__}
    settings_hash = sha256(config_path)
    contract_path = project_path(root, cfg["outputs"]["metrics"]) / "evaluation_contract.json"
    unseen_meta = contract_path.parent / "unseen/run_metadata.json"
    unseen_outputs = project_path(root, cfg["outputs"]["backtests"]) / "unseen"
    evaluated = unseen_meta.exists() or unseen_outputs.exists()
    if evaluated and (not unseen_meta.exists() or not contract_path.exists()):
        raise ValueError("Evaluated outputs exist without their metadata/contract; preserve them before continuing")
    previous = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.exists() else None
    unseen_frame, unseen_hashes = None, dict(handoff["hashes"])
    if evaluated and not historical_only:
        # Check the input before any earlier-period files or fitted objects can be replaced.
        unseen_frame = _read_prices(root, cfg, "unseen", unseen_hashes)
        prior_unseen = json.loads(unseen_meta.read_text(encoding="utf-8"))
        if prior_unseen["inputs"][cfg["unseen"]] != unseen_hashes[cfg["unseen"]]:
            raise ValueError("Evaluated unseen input changed; preserve this version and use a new output version")
    normalization, artifact_hashes, artifact_contents = {}, {}, {}
    for p in handoff["parameters"]:
        spread = spread_from_prices(handoff["prices"], p)
        relative = f"{cfg['outputs']['artifacts']}/{p['pair_id']}/normalization_2025.json"
        path = project_path(root, relative)
        identity = {k: p[k] for k in ("pair_id", "dependent", "independent", "spread_column",
                                     "evidence_label", "ols_path", "ols_sha256")}
        identity.update(model_version=cfg["model_version"], historical_sha256=handoff["hashes"][cfg["historical"]],
                        config_sha256=settings_hash, versions=versions)
        if path.exists():
            if previous is None or sha256(path) != previous["normalization"].get(relative):
                raise ValueError("Saved normalization is untracked or has changed")
            fitted = json.loads(path.read_text(encoding="utf-8"))
            year = spread.loc[cfg["normalization"]["start"]:cfg["normalization"]["end"]]
            if (any(fitted.get(k) != v for k, v in identity.items()) or fitted.get("ddof") != 1
                    or fitted.get("fit_start") != str(year.index[0].date())
                    or fitted.get("fit_end") != str(year.index[-1].date()) or fitted.get("nobs") != len(year)):
                raise ValueError("Saved normalization is incompatible with this historical fit")
            apply_normalization(spread, fitted)
        else:
            if previous is not None:
                raise ValueError("A previously saved normalization artifact is missing")
            fitted = {**fit_normalization(spread.loc[cfg["normalization"]["start"]:cfg["normalization"]["end"]]), **identity}
        content = json.dumps(fitted, indent=2, allow_nan=False) + "\n"
        loaded = json.loads(content)
        if not np.array_equal(apply_normalization(spread, loaded), apply_normalization(spread, fitted)):
            raise ValueError("Normalization reload mismatch")
        normalization[p["pair_id"]] = loaded
        artifact_contents[relative] = content
        artifact_hashes[relative] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    contract = {"config_sha256": settings_hash, "code": code_hashes,
                "historical_inputs": handoff["hashes"], "normalization": artifact_hashes}
    if evaluated:
        if previous != contract:
            raise ValueError("Evaluated run exists with different code/settings/inputs; preserve it and use a new output version")
    for relative, content in artifact_contents.items():
        path = project_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        if sha256(path) != artifact_hashes[relative]:
            raise ValueError("Saved normalization bytes differ from the frozen object")
        normalization[relative.split("/")[-2]] = json.loads(path.read_text(encoding="utf-8"))
    write_json(contract_path, contract)
    results = {}
    for period in (["historical"] if historical_only else ["historical", "unseen"]):
        hashes = dict(handoff["hashes"])
        if period == "historical":
            frame = handoff["prices"]
        elif unseen_frame is not None:
            frame, hashes = unseen_frame, unseen_hashes
        else:
            frame = _read_prices(root, cfg, period, hashes)
        combined = {key: [] for key in ("signals", "executions", "trades", "daily_account",
                                        "summary", "spread_diagnostics", "reversion_events", "zscores")}
        checks = []
        for p in handoff["parameters"]:
            fitted = normalization[p["pair_id"]]
            spread = spread_from_prices(frame, p)
            z = apply_normalization(spread, fitted)
            context = None if period == "historical" else float(apply_normalization(
                spread_from_prices(handoff["prices"].iloc[-1:], p), fitted).iloc[0])
            prices = frame[[p["dependent"] + "_Open", p["independent"] + "_Open",
                            p["dependent"] + "_Close", p["independent"] + "_Close"]].copy()
            prices.columns = ["dependent_Open", "independent_Open", "dependent_Close", "independent_Close"]
            run = simulate(prices, z, p["beta"], capital=cfg["accounting"]["initial_capital"],
                           cost_rate=cfg["accounting"]["cost_rate"], previous_z=context,
                           entry_threshold=cfg["rules"]["entry_threshold"], exit_threshold=cfg["rules"]["exit_threshold"])
            for name in ("signals", "executions", "trades", "daily_account"):
                combined[name].append(_annotate(run[name], p, period, cfg["model_version"]))
            combined["summary"].append(_annotate(pd.DataFrame([run["summary"]]), p, period, cfg["model_version"]))
            used_z = z.iloc[:len(run["daily_account"])]
            diag, events = spread_diagnostics(used_z, run["signals"])
            combined["spread_diagnostics"].append(_annotate(pd.DataFrame([diag]), p, period, cfg["model_version"]))
            combined["reversion_events"].append(_annotate(events, p, period, cfg["model_version"]))
            combined["zscores"].append(_annotate(pd.DataFrame({"Date": frame.index.strftime("%Y-%m-%d"),
                "spread": spread.to_numpy(), "zscore": z.to_numpy()}), p, period, cfg["model_version"]))
            daily, ledger, summary = run["daily_account"], run["trades"], run["summary"]
            if (summary["executed_entries"] != summary["closed_trades"] + summary["open_trades"]
                    or not np.allclose(daily["gross_equity"] - daily["net_equity"], daily["cumulative_costs"], **cfg["tolerance"])
                    or not np.isclose(ledger["net_pnl"].sum(), daily["net_pnl"].sum(), **cfg["tolerance"])
                    or not np.allclose(daily["dependent_pnl"] + daily["independent_pnl"], daily["gross_pnl"], **cfg["tolerance"])):
                raise ValueError("Trade/account reconciliation failed")
            checks += [{"check": name, "pair_id": p["pair_id"], "status": "pass"} for name in
                       ("price_coverage_and_hash", "ols_lineage_and_orientation", "historical_spread_reconstruction",
                        "normalization_2025_only_and_reload", "entry_closed_open_counts", "ledger_to_daily_pnl",
                        "leg_pnl_to_gross", "gross_net_cost_identity")]
        tables = {key: pd.concat(value, ignore_index=True) for key, value in combined.items()}
        outputs = dict(artifact_hashes)
        for name in ("signals", "executions", "trades", "daily_account"):
            _save_csv(root, f"{cfg['outputs']['backtests']}/{period}/{name}.csv", tables[name], outputs)
        for name in ("summary", "spread_diagnostics", "reversion_events"):
            _save_csv(root, f"{cfg['outputs']['metrics']}/{period}/{name}.csv", tables[name], outputs)
        _save_csv(root, f"{cfg['outputs']['zscores']}/{period}_zscores.csv", tables["zscores"], outputs)
        figure_paths = plots.save_figures(tables, cfg, project_path(root, cfg["outputs"]["figures"]) / period) if figures else []
        for relative, expected in {**hashes, **artifact_hashes}.items():
            if sha256(project_path(root, relative)) != expected:
                raise ValueError("An input or fitted object changed during the run")
        metadata = {"status": "complete" if tables["summary"]["status"].eq("complete").all() else "incomplete",
                    "period": period, "evaluation_label": "in_sample" if period == "historical" else "unseen_fixed_parameters",
                    "settings": {"sha256": settings_hash, "values": cfg}, "code": code_hashes, "versions": versions,
                    "inputs": hashes, "rows_per_pair": len(frame),
                    "actual_window": [str(frame.index[0].date()), str(frame.index[-1].date())],
                    "normalization": normalization, "validation": checks,
                    "warnings": ["Exploratory pairs; shared AMZN leg; beta-weighted holdings are not dollar-neutral",
                                 "Historical replay uses later fitted information and is in-sample"] if period == "historical"
                                else ["Exploratory pairs; shared AMZN leg; few trades cannot establish a stable return distribution"],
                    "leakage_audit": [
                        {"object": "pair/direction selection and OLS", "fit_window": ["2018-01-02", "2025-12-31"],
                         "applied_to": period, "verdict": "in-sample" if period == "historical" else "fixed before unseen"},
                        {"object": "normalization", "fit_window": ["2025-01-02", "2025-12-31"],
                         "applied_to": period, "verdict": "in-sample" if period == "historical" else "fixed before unseen"},
                        {"object": "rules and accounting", "fit_window": None,
                         "applied_to": period, "verdict": "adopted 2026-11-01 before evaluation; no tuning"}],
                    "outputs": outputs, "figures": {str(p.relative_to(root).as_posix()): sha256(p) for p in figure_paths}}
        write_json(project_path(root, cfg["outputs"]["metrics"]) / period / "run_metadata.json", metadata)
        results[period] = metadata
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/statistical_baseline.json"))
    parser.add_argument("--historical-only", action="store_true")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    matplotlib.use("Agg")
    for period, metadata in run_statistical_baseline(args.config, historical_only=args.historical_only,
                                                    figures=not args.no_figures).items():
        print(f"Statistical baseline {period}: {metadata['status']}, {metadata['rows_per_pair']} sessions per pair, "
              f"{len(metadata['validation'])} checks, {len(metadata['outputs'])} outputs")
        if metadata["status"] != "complete":
            raise RuntimeError("Statistical baseline stopped with incomplete accounts")
