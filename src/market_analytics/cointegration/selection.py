"""Select pairs from historical log prices using the adopted Phase 3 settings."""

import argparse
import itertools
import json
import math
import platform
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import statsmodels
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from statsmodels.tools.sm_exceptions import CollinearityWarning
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from market_analytics.data.master import STOCKS, project_path, sha256


def stock_pairs(stocks):
    return list(itertools.combinations(stocks, 2))


def load_config(path: Path) -> tuple[Path, dict]:
    path = path.resolve()
    root = path.parent.parent
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if tuple(cfg["stocks"]) != STOCKS:
        raise ValueError("Pair selection must use the six stocks in their recorded order")
    if cfg["input"] != "data/processed/master_historical.csv":
        raise ValueError("Pair selection reads the historical master only")
    if pd.Timestamp(cfg["period"]["end"]) >= pd.Timestamp("2026-01-01"):
        raise ValueError("Pair selection must end before 2026")
    if cfg["multiplicity"]["family_size"] != len(stock_pairs(STOCKS)):
        raise ValueError("The multiple-testing family must include all 15 pairs")
    if (cfg["multiplicity"]["direction_multiplier"] != 2 or cfg["multiplicity"]["method"] != "holm"
            or cfg["ranking"] != ["method_agreement", "eg_pvalue", "pair_order"]):
        raise ValueError("The config differs from the implemented, adopted selection rules")
    if not 0 < cfg["alpha"] < 1 or not 1 <= cfg["shortlist_size"] <= 15:
        raise ValueError("Invalid significance level or shortlist size")
    if not 1 <= cfg["johansen"]["min_levels_lag"] <= cfg["johansen"]["max_levels_lag"]:
        raise ValueError("Johansen requires a positive levels lag")
    return root, cfg


def read_input(root: Path, cfg: dict) -> tuple[pd.DataFrame, str]:
    path = project_path(root, cfg["input"])
    manifest = json.loads(project_path(root, cfg["manifest"]).read_text(encoding="utf-8"))
    expected = manifest["outputs"].get(cfg["input"])
    actual = sha256(path)
    if expected is None or actual != expected:
        raise ValueError("Historical input does not match its manifest hash")
    columns = [f"{s}_Close" for s in cfg["stocks"]]
    frame = pd.read_csv(path, usecols=["Date"] + columns, parse_dates=["Date"]).set_index("Date")
    return frame[columns], actual


def check(name, count, details=""):
    return {"check": name, "status": "pass", "count": int(count), "details": details}


def validate_input(frame: pd.DataFrame, cfg: dict) -> list[dict]:
    dates, period = frame.index, cfg["period"]
    if (not isinstance(dates, pd.DatetimeIndex) or len(dates) == 0 or dates.hasnans
            or dates.has_duplicates or not dates.is_monotonic_increasing or dates.tz is not None
            or not dates.equals(dates.normalize())):
        raise ValueError("Historical dates must be unique, increasing daily dates")
    if (dates[0] < pd.Timestamp(period["start"]) or dates[-1] > pd.Timestamp(period["end"])
            or dates[-1] >= pd.Timestamp("2026-01-01")):
        raise ValueError("Input contains dates outside the historical period")
    if (len(frame) != period["rows"] or str(dates[0].date()) != period["first_session"]
            or str(dates[-1].date()) != period["last_session"]):
        raise ValueError("Historical coverage differs from the recorded sessions")
    columns = [f"{s}_Close" for s in cfg["stocks"]]
    if set(frame.columns) != set(columns):
        raise ValueError("Expected only the six Close columns")
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all() or not (values > 0).all():
        raise ValueError("Historical Close prices must be finite and positive")
    if any(np.ptp(values[:, i]) == 0 for i in range(len(columns))):
        raise ValueError("A stock has constant prices")
    return [check("historical_dates_and_coverage", len(frame)),
            check("six_positive_finite_close_columns", values.size)]


def dates_used(values: pd.Series) -> dict:
    return {"fit_start": str(values.index[0].date()), "fit_end": str(values.index[-1].date()),
            "nobs": len(values)}


def require_finite(values, label):
    if not np.isfinite(np.asarray(values, dtype=float)).all():
        raise ValueError(f"Non-finite {label}")


def max_adf_lag(n: int, regression: str, cfg: dict) -> int:
    settings = cfg["adf"]
    d = {"n": 0, "c": 1, "ct": 2}[regression]
    rule = settings["maxlag_multiplier"] * (n / settings["maxlag_divisor"]) ** settings["maxlag_power"]
    lag = min(math.ceil(rule), n // 2 - d - 1)
    if lag < 0 or n < 5:
        raise ValueError("Too few observations for ADF")
    return lag


def adf_result(values: pd.Series, regression: str, cfg: dict) -> dict:
    require_finite(values, "ADF input")
    if np.ptp(values.to_numpy()) == 0:
        raise ValueError("ADF input is constant")
    limit = max_adf_lag(len(values), regression, cfg)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = adfuller(values.to_numpy(), maxlag=limit, regression=regression,
                          autolag=cfg["adf"]["autolag"], result_object=True)
    require_finite([result.statistic, result.pvalue, *result.critical_values.values()], "ADF result")
    if not 0 <= result.pvalue <= 1:
        raise ValueError("Invalid ADF p-value")
    critical = {f"critical_{key.rstrip('%')}": float(value)
                for key, value in result.critical_values.items()}
    return {**dates_used(values), "regression": regression, "autolag": cfg["adf"]["autolag"],
            "maxlag": limit, "usedlag": int(result.lags), "effective_nobs": int(result.nobs),
            "effective_start": str(values.index[len(values)-result.nobs].date()),
            "statistic": float(result.statistic), "pvalue": float(result.pvalue), **critical}


def integration_tests(logs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows = []
    for symbol in cfg["stocks"]:
        level = adf_result(logs[symbol], cfg["adf"]["level_regression"], cfg)
        difference = adf_result(logs[symbol].diff().iloc[1:], cfg["adf"]["difference_regression"], cfg)
        consistent = level["pvalue"] > cfg["alpha"] and difference["pvalue"] <= cfg["alpha"]
        status = "consistent_with_i1" if consistent else "assumption_warning"
        for transform, row in [("log_level", level), ("first_difference", difference)]:
            rows.append({"symbol": symbol, "transform": transform, **row,
                         "reject_unit_root": row["pvalue"] <= cfg["alpha"], "i1_status": status})
    return pd.DataFrame(rows)


def fit_ols(y: pd.Series, x: pd.Series) -> tuple[dict, pd.Series]:
    if not y.index.equals(x.index) or len(y) < 3:
        raise ValueError("OLS inputs must share at least three dated observations")
    require_finite(y, "OLS dependent input")
    require_finite(x, "OLS independent input")
    if np.ptp(x.to_numpy()) == 0 or np.ptp(y.to_numpy()) == 0:
        raise ValueError("OLS input is constant")
    design = np.column_stack([np.ones(len(x)), x.to_numpy()])
    if np.linalg.matrix_rank(design) != 2:
        raise ValueError("OLS design is singular")
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        fit = sm.OLS(y.to_numpy(), design).fit()
    require_finite([*fit.params, fit.rsquared, *fit.resid], "OLS fit")
    row = {**dates_used(y), "intercept": float(fit.params[0]), "beta": float(fit.params[1]),
           "r_squared": float(fit.rsquared)}
    return row, pd.Series(fit.resid, index=y.index)


def directional_test(logs: pd.DataFrame, dependent: str, independent: str,
                     cfg: dict) -> tuple[dict, pd.Series]:
    a, b = sorted([dependent, independent], key=cfg["stocks"].index)
    row, residual = fit_ols(logs[dependent], logs[independent])
    limit = max_adf_lag(len(logs), cfg["adf"]["residual_regression"], cfg)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", CollinearityWarning)
            warnings.simplefilter("error", RuntimeWarning)
            statistic, pvalue, critical = coint(
                logs[dependent].to_numpy(), logs[independent].to_numpy(),
                **cfg["engle_granger"], maxlag=limit, autolag=cfg["adf"]["autolag"])
    except (Warning, np.linalg.LinAlgError) as exc:
        raise ValueError(f"Failed Engle-Granger fit for {dependent} on {independent}: {exc}") from exc
    require_finite([statistic, pvalue, *critical], "Engle-Granger result")
    if not 0 <= pvalue <= 1:
        raise ValueError("Invalid Engle-Granger p-value")
    adf = adf_result(residual, cfg["adf"]["residual_regression"], cfg)
    if not np.isclose(statistic, adf["statistic"], **cfg["tolerance"]):
        raise ValueError("Residual ADF and Engle-Granger statistics disagree")
    row.update(pair_id=f"{a}_{b}", dependent=dependent, independent=independent,
               direction_order=int(dependent != a), spread_column=f"{dependent}_on_{independent}",
               eg_statistic=float(statistic), eg_pvalue=float(pvalue),
               eg_reject=bool(pvalue <= cfg["alpha"]),
               eg_critical_1=float(critical[0]), eg_critical_5=float(critical[1]),
               eg_critical_10=float(critical[2]), eg_trend=cfg["engle_granger"]["trend"],
               residual_regression=cfg["adf"]["residual_regression"],
               residual_adf_statistic=adf["statistic"], maxlag=limit, usedlag=adf["usedlag"],
               effective_nobs=adf["effective_nobs"], effective_start=adf["effective_start"],
               status="ok")
    return row, residual


def select_levels_lag(bic, min_lag=1) -> int:
    require_finite(bic, "VAR BIC curve")
    if len(bic) <= min_lag:
        raise ValueError("No eligible VAR lag order")
    return int(np.argmin(np.asarray(bic)[min_lag:])) + min_lag


def sequential_rank(statistics, critical_values) -> int:
    require_finite([statistics, critical_values], "Johansen rank inputs")
    tests = enumerate(zip(statistics, critical_values, strict=True))
    return next((r for r, (stat, critical) in tests if stat <= critical), len(statistics))


def johansen_test(logs, a, b, cfg):
    settings = cfg["johansen"]
    pair_id = f"{a}_{b}"
    matrix = logs[[a, b]].to_numpy()
    orders = VAR(matrix).select_order(maxlags=settings["max_levels_lag"], trend=settings["var_trend"])
    bic = orders.ics[settings["criterion"]]
    p = select_levels_lag(bic, settings["min_levels_lag"])
    with warnings.catch_warnings(record=True) as messages:
        warnings.simplefilter("always")
        result = coint_johansen(matrix, settings["det_order"], p-1)
    complex_parts = np.any(np.imag(result.eig) != 0) or np.any(np.imag(result.evec) != 0)
    if complex_parts:
        raise ValueError(f"Complex Johansen eigenvalues or eigenvectors for {pair_id}")
    # NumPy can return complex dtype with exactly real eigenvalues. In that
    # case statsmodels warns while casting the trace statistics to real.
    for message in messages:
        if not issubclass(message.category, np.exceptions.ComplexWarning):
            raise ValueError(f"Johansen warning for {pair_id}: {message.message}")
    require_finite([*np.real(result.eig), *result.trace_stat, *result.max_eig_stat,
                    *result.trace_stat_crit_vals.ravel(), *result.max_eig_stat_crit_vals.ravel()],
                   "Johansen result")
    if np.any(np.real(result.eig) < 0) or np.any(np.real(result.eig) >= 1):
        raise ValueError(f"Invalid Johansen eigenvalues for {pair_id}")
    row = {"pair_id": pair_id, **dates_used(logs[a]), "levels_lag": p, "k_ar_diff": p-1,
           "effective_nobs": len(logs)-p, "effective_start": str(logs.index[p].date()),
           "det_order": settings["det_order"], "lag_at_upper_bound": p == settings["max_levels_lag"],
           "status": "ok"}
    for name, statistics, critical in [("trace", result.trace_stat, result.trace_stat_crit_vals),
                                       ("max_eig", result.max_eig_stat, result.max_eig_stat_crit_vals)]:
        for r in range(2):
            row[f"{name}_stat_r{r}"] = float(statistics[r])
            for col, confidence in enumerate(settings["confidence_levels"]):
                row[f"{name}_critical_r{r}_{confidence}"] = float(critical[r, col])
        for col, confidence in enumerate(settings["confidence_levels"]):
            row[f"{name}_rank_{confidence}"] = sequential_rank(statistics, critical[:, col])
    curve = [{"pair_id": pair_id, "levels_lag": i, "bic": float(score),
              "eligible": i >= settings["min_levels_lag"], "selected": i == p,
              "fit_start": str(logs.index[settings["max_levels_lag"]].date()),
              "fit_end": str(logs.index[-1].date()), "nobs": len(logs)-settings["max_levels_lag"]}
             for i, score in enumerate(bic)]
    notes = []
    if messages:
        notes.append({"pair_id": pair_id, "kind": "real_eigenvalues_in_complex_dtype",
                      "count": len(messages), "message": str(messages[0].message)})
    if row["lag_at_upper_bound"]:
        notes.append({"pair_id": pair_id, "kind": "lag_upper_bound", "count": 1,
                      "message": "BIC chose the largest eligible order; search not expanded"})
    return row, curve, notes


def adjust_pair_pvalues(first, second, alpha):
    require_finite([first, second], "directional p-values")
    raw = np.asarray([first, second], dtype=float)
    if np.any(raw < 0) or np.any(raw > 1):
        raise ValueError("P-values must lie in [0, 1]")
    pair = np.minimum(1., 2 * np.minimum(raw[0], raw[1]))
    return pair, multipletests(pair, alpha=alpha, method="holm")[1]


def rank_pairs(directional, johansen, integration, cfg):
    canonical = [f"{a}_{b}" for a, b in stock_pairs(cfg["stocks"])]
    selected = (directional.sort_values(["eg_pvalue", "direction_order"], kind="stable")
                .drop_duplicates("pair_id").copy())
    by_order = {order: directional[directional.direction_order == order]
                .set_index("pair_id").loc[canonical, "eg_pvalue"] for order in (0, 1)}
    pair_p, adjusted = adjust_pair_pvalues(by_order[0].to_numpy(), by_order[1].to_numpy(), cfg["alpha"])
    correction = pd.DataFrame({"pair_id": canonical, "pair_order": range(15),
                               "eg_pair_pvalue": pair_p, "holm_pair_pvalue": adjusted})
    selected = (selected.merge(correction, on="pair_id", validate="one_to_one")
                .merge(johansen, on="pair_id", suffixes=("", "_johansen"), validate="one_to_one"))
    assumptions = integration.drop_duplicates("symbol").set_index("symbol").i1_status.to_dict()
    selected["i1_consistent"] = [assumptions[y] == assumptions[x] == "consistent_with_i1"
                                 for y, x in zip(selected.dependent, selected.independent)]
    selected["eg_reject"] = selected.eg_pvalue <= cfg["alpha"]
    selected["johansen_reject"] = selected.trace_rank_95 == 1
    selected["method_count"] = selected.eg_reject.astype(int) + selected.johansen_reject.astype(int)
    selected["method_agreement"] = selected.method_count.map({2: "both", 1: "one", 0: "neither"})
    selected["holm_reject"] = selected.holm_pair_pvalue <= cfg["alpha"]
    supported = selected.i1_consistent & selected.holm_reject & selected.johansen_reject
    selected["evidence_label"] = np.where(supported, "supported", "exploratory")
    selected = selected.sort_values(["method_count", "eg_pvalue", "pair_order"],
                                    ascending=[False, True, True], kind="stable").reset_index(drop=True)
    selected.insert(0, "rank", np.arange(1, len(selected)+1))
    selected["shortlisted"] = selected["rank"] <= cfg["shortlist_size"]
    return selected


def half_life(spread):
    base = {**dates_used(spread), "phi": np.nan, "half_life_sessions": np.nan}
    if len(spread) < 4:
        return {**base, "status": "insufficient_observations"}
    if np.ptp(spread.to_numpy()) == 0:
        return {**base, "status": "constant_spread"}
    require_finite(spread, "half-life input")
    design = np.column_stack([np.ones(len(spread)-1), spread.iloc[:-1]])
    if np.linalg.matrix_rank(design) != 2:
        raise ValueError("Half-life regression has constant lagged inputs")
    # A zero AR coefficient can have a constant dependent series. R-squared
    # is undefined there, but the intercept and slope are still estimable.
    coefficients = np.linalg.lstsq(design, spread.iloc[1:], rcond=None)[0]
    require_finite(coefficients, "half-life fit")
    phi = float(coefficients[1])
    status = "ok" if 0 < phi < 1 else "nonpositive_phi" if phi <= 0 else "non_mean_reverting"
    return {**base, "effective_start": str(spread.index[1].date()), "effective_nobs": len(spread)-1,
            "phi": phi, "ar_intercept": float(coefficients[0]),
            "half_life_sessions": -math.log(2)/math.log(phi) if status == "ok" else np.nan,
            "status": status}


def reconstruct_spread(prices, parameters):
    dependent = np.log(prices[f"{parameters['dependent']}_Close"])
    independent = np.log(prices[f"{parameters['independent']}_Close"])
    return dependent - parameters["intercept"] - parameters["beta"] * independent


def shortlist_reason(row):
    i1 = "consistent" if row["i1_consistent"] else "flagged"
    return (f"Rank {row['rank']}: {row['method_agreement']} method agreement; "
            f"EG p={row['eg_pvalue']:.6g}; pair Holm p={row['holm_pair_pvalue']:.6g}; "
            f"trace rank={row['trace_rank_95']}; I(1) diagnostics {i1}. "
            f"{row['evidence_label'].capitalize()}.")


def analyse(frame: pd.DataFrame, cfg: dict):
    checks = validate_input(frame, cfg)
    logs = np.log(frame[[f"{s}_Close" for s in cfg["stocks"]]]).set_axis(cfg["stocks"], axis=1)
    integration = integration_tests(logs, cfg)
    directions, johansen, curves, notes, residuals = [], [], [], [], {}
    for a, b in stock_pairs(cfg["stocks"]):
        for y, x in [(a, b), (b, a)]:
            row, residual = directional_test(logs, y, x, cfg)
            directions.append(row)
            residuals[row["spread_column"]] = residual
            design = np.column_stack([np.ones(len(logs)), logs[x]])
            independent = np.linalg.lstsq(design, logs[y], rcond=None)[0]
            if not np.allclose([row["intercept"], row["beta"]], independent, **cfg["tolerance"]):
                raise ValueError("Independent OLS coefficients disagree")
        result, curve, warnings_found = johansen_test(logs, a, b, cfg)
        johansen.append(result)
        curves.extend(curve)
        notes.extend(warnings_found)
    directional, johansen = pd.DataFrame(directions), pd.DataFrame(johansen)
    ranking = rank_pairs(directional, johansen, integration, cfg)
    canonical = ranking.sort_values("pair_order")
    spreads = pd.DataFrame({row.spread_column: residuals[row.spread_column] for row in canonical.itertuples()},
                           index=frame.index).rename_axis("Date")
    halves, stability = [], []
    for row in canonical.to_dict("records"):
        reconstructed = reconstruct_spread(frame, row)
        if not np.allclose(reconstructed, spreads[row["spread_column"]], **cfg["tolerance"]):
            raise ValueError("Saved coefficients cannot reconstruct the spread")
        halves.append({"pair_id": row["pair_id"], "spread_column": row["spread_column"],
                       **half_life(spreads[row["spread_column"]])})
        for period in cfg["stability_periods"]:
            subset = logs.loc[period["start"]:period["end"]]
            fit, _ = fit_ols(subset[row["dependent"]], subset[row["independent"]])
            stability.append({"pair_id": row["pair_id"], "period": period["name"],
                              "dependent": row["dependent"], "independent": row["independent"], **fit})
    halves, stability = pd.DataFrame(halves), pd.DataFrame(stability)
    half_columns = halves[["pair_id", "phi", "half_life_sessions", "status"]]
    ranking = ranking.merge(half_columns.rename(columns={"status": "half_life_status"}),
                            on="pair_id", validate="one_to_one")
    first, second = cfg["stability_periods"]
    betas = stability.pivot(index="pair_id", columns="period", values="beta")
    ranking["beta_change_abs"] = ranking.pair_id.map((betas[second["name"]]-betas[first["name"]]).abs())
    sign_changed = np.sign(betas[first["name"]]) != np.sign(betas[second["name"]])
    ranking["beta_sign_changed"] = ranking.pair_id.map(sign_changed)
    ranking["nonpositive_beta"] = ranking.beta <= 0
    ranking["reason"] = [shortlist_reason(r) for r in ranking.to_dict("records")]
    tables = {"integration_tests": integration, "directional_tests": directional,
              "lag_selection": pd.DataFrame(curves), "johansen_tests": johansen,
              "pair_ranking": ranking, "shortlist": ranking[ranking.shortlisted].copy(),
              "half_life": halves, "hedge_stability": stability}
    counts = {"integration_tests": 12, "directional_tests": 30,
              "lag_selection": 15*(cfg["johansen"]["max_levels_lag"]+1), "johansen_tests": 15,
              "pair_ranking": 15, "shortlist": cfg["shortlist_size"], "half_life": 15,
              "hedge_stability": 30}
    for name, count in counts.items():
        if len(tables[name]) != count:
            raise ValueError(f"Unexpected number of rows in {name}")
        checks.append(check(f"{name}_rows", count))
    require_finite(spreads, "historical spreads")
    checks += [check("independent_ols_coefficients", 30), check("residual_adf_matches_engle_granger", 30),
               check("spread_reconstruction", 15), check("historical_spread_grid", spreads.size)]
    return tables, spreads, checks, notes


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def leakage_audit(tables, start, end):
    periods = tables["hedge_stability"][["period", "fit_start", "fit_end"]].drop_duplicates()
    return [
        {"object": "integration and lag choices", "fit_window": [start, end],
         "applied_to": "historical test specifications", "verdict": "historical only"},
        {"object": "pair and direction selection", "fit_window": [start, end],
         "applied_to": "shortlist for later evaluation",
         "verdict": "no 2026 input; later LSTM validation is conditional on this shortlist"},
        {"object": "full-history OLS coefficients", "fit_window": [start, end],
         "applied_to": "in-sample residuals and the future Phase 4 handoff",
         "verdict": "in-sample residuals are not out-of-sample evidence"},
        {"object": "hedge stability fits", "fit_window": periods.to_dict("records"),
         "applied_to": "historical diagnostics only", "verdict": "does not change fitted trading coefficients"}]


def run_pair_selection(config_path: Path, *, figures=True):
    from market_analytics.cointegration import plots

    root, cfg = load_config(config_path)
    frame, input_hash = read_input(root, cfg)
    tables, spreads, checks, notes = analyse(frame, cfg)
    metrics = project_path(root, cfg["outputs"]["metrics"])
    metrics.mkdir(parents=True, exist_ok=True)
    saved = []
    for name, table in tables.items():
        path = metrics / f"{name}.csv"
        table.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
        saved.append(path)
    path = project_path(root, cfg["outputs"]["spreads"])
    path.parent.mkdir(parents=True, exist_ok=True)
    spreads.to_csv(path, lineterminator="\n", float_format="%.17g")
    saved.append(path)
    versions = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                "statsmodels": statsmodels.__version__, "matplotlib": matplotlib.__version__}
    config_hash = sha256(config_path.resolve())
    keys = ["pair_id", "dependent", "independent", "spread_column", "intercept", "beta",
            "fit_start", "fit_end", "nobs", "evidence_label", "shortlisted"]
    for row in tables["pair_ranking"].to_dict("records"):
        parameters = {key: row[key] for key in keys}
        parameters.update(model_version=cfg["model_version"],
                          transformation="natural log of Yahoo Close; dividends excluded",
                          spread_formula="log(dependent_Close) - intercept - beta * log(independent_Close)",
                          input_sha256=input_hash, settings_sha256=config_hash, versions=versions)
        filename = f"ols_{row['fit_start'].replace('-', '')}_{row['fit_end'].replace('-', '')}.json"
        path = project_path(root, cfg["outputs"]["artifacts"]) / row["pair_id"] / filename
        write_json(path, parameters)
        reloaded = json.loads(path.read_text(encoding="utf-8"))
        if not np.allclose(reconstruct_spread(frame, reloaded), spreads[row["spread_column"]], **cfg["tolerance"]):
            raise ValueError("Reloaded artifact does not reconstruct the historical spread")
        saved.append(path)
    checks.append(check("reloaded_parameters_reproduce_spreads", 15))
    figure_paths = []
    if figures:
        figure_paths = plots.save_figures(frame, tables, spreads, cfg,
                                          project_path(root, cfg["outputs"]["figures"]))
    if sha256(project_path(root, cfg["input"])) != input_hash:
        raise ValueError("The historical master changed during pair selection")
    checks.append(check("input_unchanged_after_run", 1))
    start, end = str(frame.index[0].date()), str(frame.index[-1].date())
    code_files = [Path(__file__).resolve(), Path(plots.__file__).resolve(), root / "scripts/run_pair_selection.py"]
    metadata = {
        "status": "complete",
        "input": {"file": cfg["input"], "sha256": input_hash, "manifest": cfg["manifest"],
                  "rows": len(frame), "first_date": start, "last_date": end},
        "settings": {"file": config_path.resolve().relative_to(root).as_posix(), "sha256": config_hash,
                     "values": cfg},
        "versions": versions, "validation": checks, "warnings": notes,
        "code": {p.relative_to(root).as_posix(): sha256(p) for p in code_files},
        "lock_sha256": sha256(root / "uv.lock"),
        "outputs": {p.relative_to(root).as_posix(): sha256(p) for p in saved},
        "figures": [p.relative_to(root).as_posix() for p in figure_paths],
        "leakage_audit": leakage_audit(tables, start, end),
        "conventions": {"multiplicity": "min(1, 2 * min(directional EG p)); Holm over 15 pairs",
                        "ranking": "both methods, one, neither; raw selected EG p; canonical pair order",
                        "pvalue_rule": "p <= alpha; Johansen statistic > critical value",
                        "normalization": "not estimated in Phase 3", "random_seed": None}}
    write_json(metrics / "run_metadata.json", metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/pair_selection.json"))
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    matplotlib.use("Agg")
    metadata = run_pair_selection(args.config, figures=not args.no_figures)
    print(f"Pair selection: {metadata['input']['rows']} historical sessions, "
          f"{len(metadata['validation'])} checks, {len(metadata['outputs'])} saved tables/data/artifacts, "
          f"{len(metadata['figures'])} figures")
