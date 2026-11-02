"""Test one pair with the Phase 3 settings and, when shown, build its Z-scores and Phase 4 signals."""

import copy

import numpy as np
import pandas as pd

from market_analytics.api.prices import InputError, tickers as price_tickers
from market_analytics.cointegration.selection import (
    adjust_pair_pvalues, directional_test, integration_tests, johansen_test, reconstruct_spread,
)
from market_analytics.data.master import STOCKS
from market_analytics.trading.baseline import apply_normalization
from market_analytics.trading.signals import decide_signal

# A signal at one close is filled before the next decision, as in the Phase 4 backtest.
POSITION_AFTER = {"enter_long": 1, "enter_short": -1, "exit": 0}


def order_tickers(pair):
    """Use the Phase 3 order for two project tickers, so pair IDs match its tables."""
    if all(t in STOCKS for t in pair):
        return sorted(pair, key=STOCKS.index)
    return list(pair)


def split_sessions(index, fit_end, min_fit, min_later):
    """Return a boolean mask of fitting sessions; the fit end need not be a session."""
    fitting = np.asarray(index <= fit_end)
    n_fit, n_later = int(fitting.sum()), int((~fitting).sum())
    if n_fit < min_fit:
        raise InputError(f"{n_fit} sessions fall on or before {fit_end.date()}; "
                         f"at least {min_fit} are needed for the tests")
    if n_later < min_later:
        raise InputError(f"{n_later} sessions fall after {fit_end.date()}; at least {min_later} are needed")
    return fitting


def fit_window_normalization(spread, fit_end, years=1):
    """Mean and ddof=1 standard deviation over the sessions in the final year up to the fit end."""
    start = fit_end - pd.DateOffset(years=years)
    window = spread[(spread.index > start) & (spread.index <= fit_end)]
    if len(window) < 2:
        raise InputError("Fewer than two sessions fall in the normalization window")
    mean, std = float(window.mean()), float(window.std(ddof=1))
    if not np.isfinite([mean, std]).all() or std <= 0:
        raise InputError("The spread is constant over the normalization window")
    return {"mean": mean, "std": std, "ddof": 1, "fit_start": str(window.index[0].date()),
            "fit_end": str(window.index[-1].date()), "nobs": len(window)}


def decide(first_pvalue, second_pvalue, trace_rank, alpha):
    """Combine the two directional Engle-Granger p-values and the Johansen rank into a verdict."""
    pair, _ = adjust_pair_pvalues(np.array([first_pvalue]), np.array([second_pvalue]), alpha)
    adjusted = float(pair[0])
    eg_pass, johansen_pass = adjusted <= alpha, int(trace_rank) == 1
    return {"eg_pair_pvalue": adjusted, "eg_pass": eg_pass, "johansen_pass": johansen_pass,
            "cointegrated": eg_pass and johansen_pass}


def walk_signals(zscores, previous_z, entry_threshold, exit_threshold):
    """Apply the Phase 4 rules to each session, starting flat."""
    rows, position = [], 0
    for day, value in zscores.items():
        z = float(value)
        decision = decide_signal(previous_z, z, position, entry_threshold, exit_threshold)
        rows.append({"date": str(day.date()), "previous_z": previous_z, "zscore": z,
                     "position": position, **decision})
        position = POSITION_AFTER.get(decision["action"], position)
        previous_z = z
    return rows


def count_signals(rows):
    return {"long_crossings": sum(r["long_crossing"] for r in rows),
            "short_crossings": sum(r["short_crossing"] for r in rows),
            "long_entries": sum(r["action"] == "enter_long" for r in rows),
            "short_entries": sum(r["action"] == "enter_short" for r in rows),
            "exits": sum(r["action"] == "exit" for r in rows)}


def phase3_note(ranking, pair_id):
    """The Phase 3 evidence for a project pair, or None for other tickers."""
    match = ranking[ranking.pair_id == pair_id]
    if match.empty:
        return None
    row = match.iloc[0]
    return {"rank": int(row["rank"]), "evidence_label": str(row["evidence_label"]),
            "dependent": str(row["dependent"]), "independent": str(row["independent"]),
            "eg_pvalue": float(row["eg_pvalue"]), "holm_pair_pvalue": float(row["holm_pair_pvalue"]),
            "note": (f"Phase 3 tested all 15 pairs together and labelled this pair "
                     f"{row['evidence_label']}. Testing one pair picked from that ranking "
                     "overstates the evidence, because the pick already used the same prices.")}


def analyse_pair(prices, fit_end, pair_cfg, rules, settings, *, exploratory=False, ranking=None):
    """Run the single-pair analysis on a parsed price frame and return plain JSON-ready values."""
    a, b = order_tickers(price_tickers(prices))
    fit_end = pd.Timestamp(fit_end)
    fitting = split_sessions(prices.index, fit_end, settings["min_fit_sessions"],
                             settings["min_later_sessions"])
    cfg = copy.deepcopy(pair_cfg)
    cfg["stocks"] = [a, b]
    logs = np.log(prices[[f"{a}_Close", f"{b}_Close"]]).set_axis([a, b], axis=1)
    fit_logs = logs[fitting]
    try:
        integration = integration_tests(fit_logs, cfg)
        directions = [directional_test(fit_logs, y, x, cfg)[0] for y, x in [(a, b), (b, a)]]
        johansen, _, notes = johansen_test(fit_logs, a, b, cfg)
    except (ValueError, np.linalg.LinAlgError) as exc:
        raise InputError(f"The tests could not be run on these prices: {exc}") from exc
    alpha = cfg["alpha"]
    verdict = decide(directions[0]["eg_pvalue"], directions[1]["eg_pvalue"],
                     johansen["trace_rank_95"], alpha)
    # Same tie-break as Phase 3: the smaller p-value, then the canonical direction.
    kept = min(directions, key=lambda r: (r["eg_pvalue"], r["direction_order"]))

    warnings = []
    for row in integration.drop_duplicates("symbol").itertuples():
        if row.i1_status != "consistent_with_i1":
            warnings.append(f"{row.symbol}: the ADF results on the fitting sessions do not look like "
                            "an I(1) series, so the cointegration tests may be unreliable")
    warnings += [n["message"] for n in notes if n["kind"] == "lag_upper_bound"]
    pair_id = f"{a}_{b}"
    phase3 = phase3_note(ranking, pair_id) if ranking is not None else None

    result = {
        "pair_id": pair_id, "tickers": [a, b], "project_pair": phase3 is not None,
        "fit": {"fit_end": str(fit_end.date()), "first_session": str(prices.index[0].date()),
                "last_fit_session": str(prices.index[fitting][-1].date()),
                "last_session": str(prices.index[-1].date()),
                "fit_sessions": int(fitting.sum()), "later_sessions": int((~fitting).sum())},
        "tests": {
            "alpha": alpha,
            "directions": [{k: r[k] for k in ("dependent", "independent", "intercept", "beta", "r_squared",
                                               "eg_statistic", "eg_pvalue", "eg_critical_5", "usedlag")}
                           for r in directions],
            "kept_dependent": kept["dependent"], "kept_independent": kept["independent"],
            "johansen": {k: johansen[k] for k in ("levels_lag", "trace_stat_r0", "trace_critical_r0_95",
                                                  "trace_stat_r1", "trace_critical_r1_95", "trace_rank_95")},
            **verdict,
        },
        "integration": [{"symbol": r["symbol"], "transform": r["transform"], "pvalue": r["pvalue"],
                         "i1_status": r["i1_status"]} for r in integration.to_dict("records")],
        "warnings": warnings, "phase3": phase3,
        "view": "cointegrated" if verdict["cointegrated"] else "exploratory" if exploratory else "tests_only",
        "regression": None, "normalization": None, "series": None, "signals": None, "signal_counts": None,
    }
    if result["view"] == "tests_only":
        return result

    spread = reconstruct_spread(prices, kept)
    normalization = fit_window_normalization(spread[fitting], fit_end, settings["normalization_years"])
    z = apply_normalization(spread, normalization)
    signals = walk_signals(z[~fitting], float(z[fitting].iloc[-1]),
                           rules["entry_threshold"], rules["exit_threshold"])
    result.update(
        regression={k: kept[k] for k in ("dependent", "independent", "intercept", "beta")},
        normalization=normalization,
        series=[{"date": str(day.date()), "spread": float(s), "zscore": float(v), "fitting": bool(f)}
                for day, s, v, f in zip(spread.index, spread, z, fitting)],
        signals=signals, signal_counts=count_signals(signals),
    )
    return result
