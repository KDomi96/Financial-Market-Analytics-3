"""Execute dated decisions at the following Open and account for both stock legs."""

import numpy as np
import pandas as pd

from market_analytics.trading.signals import decide_signal


PRICE_COLUMNS = ["dependent_Open", "independent_Open", "dependent_Close", "independent_Close"]
EXECUTION_COLUMNS = ["Date", "signal_date", "trade_id", "action", "leg", "shares_change",
                     "price", "turnover", "cost"]
TRADE_COLUMNS = ["trade_id", "direction", "entry_signal_date", "entry_date", "exit_signal_date",
                 "exit_date", "mark_date", "status", "q_dependent", "q_independent",
                 "entry_dependent", "entry_independent", "mark_dependent", "mark_independent",
                 "entry_gross_notional", "entry_net_exposure", "mark_net_exposure",
                 "dependent_pnl", "independent_pnl", "gross_pnl", "costs", "net_pnl",
                 "gross_return", "net_return", "holding_sessions"]


def share_quantities(notional, beta, opens, direction):
    """Translate the dependent-leg notional and log-price beta into fixed shares."""
    values = np.asarray(opens, dtype=float)
    if (values.shape != (2,) or not np.isfinite(values).all() or (values <= 0).any()
            or not np.isfinite([notional, beta]).all() or notional <= 0 or beta <= 0
            or direction not in (-1, 1)):
        raise ValueError("Sizing needs positive finite prices, notional, beta, and a direction")
    return direction * notional * np.array([1., -beta]) / values


def entry_quantities(capital, equity, cost_rate, beta, opens, direction):
    if not np.isfinite([capital, equity, cost_rate]).all() or min(capital, equity) <= 0 or cost_rate < 0:
        raise ValueError("Invalid capital, equity, or transaction cost")
    gross = min(capital, equity) / (1 + cost_rate)
    return share_quantities(gross / (1 + abs(beta)), beta, opens, direction)


def _trade_record(active, mark, date, index, exit_signal_date="", closed=False):
    pnl = active["q"] * (mark - active["prices"])
    gross = float(pnl.sum())
    net = gross - active["costs"]
    return {"trade_id": active["trade_id"], "direction": active["direction"],
            "entry_signal_date": active["signal_date"], "entry_date": active["date"],
            "exit_signal_date": exit_signal_date, "exit_date": date if closed else "",
            "mark_date": date, "status": "closed" if closed else "open",
            "q_dependent": active["q"][0], "q_independent": active["q"][1],
            "entry_dependent": active["prices"][0], "entry_independent": active["prices"][1],
            "mark_dependent": mark[0], "mark_independent": mark[1],
            "entry_gross_notional": active["gross"],
            "entry_net_exposure": float(active["q"] @ active["prices"]),
            "mark_net_exposure": float(active["q"] @ mark),
            "dependent_pnl": pnl[0], "independent_pnl": pnl[1], "gross_pnl": gross,
            "costs": active["costs"], "net_pnl": net, "gross_return": gross / active["gross"],
            "net_return": net / active["gross"], "holding_sessions": index - active["index"]}


def summarize(tables, capital, status):
    signals, trades, daily = (tables[k] for k in ("signals", "trades", "daily_account"))
    closed = trades.loc[trades["status"].eq("closed")]
    opened = trades.loc[trades["status"].eq("open")]
    last = daily.iloc[-1]
    summary = {"status": status, "sessions": len(daily), "initial_capital": capital,
               "executed_entries": len(trades), "closed_trades": len(closed), "open_trades": len(opened),
               "win_rate": float((closed["net_pnl"] > 0).mean()) if len(closed) else np.nan,
               "trade_metric_status": "defined" if len(closed) else "no_closed_trades",
               "mean_closed_trade_return": closed["net_return"].mean(),
               "mean_closed_holding_sessions": closed["holding_sessions"].mean(),
               "closed_net_pnl": closed["net_pnl"].sum(), "open_net_pnl": opened["net_pnl"].sum(),
               "final_net_equity": last["net_equity"], "final_gross_equity": last["gross_equity"],
               "net_return": (last["net_equity"] - capital) / capital,
               "gross_return": (last["gross_equity"] - capital) / capital,
               "total_costs": last["cumulative_costs"],
               "dependent_pnl": daily["dependent_pnl"].sum(),
               "independent_pnl": daily["independent_pnl"].sum(),
               "max_drawdown_net": daily["net_drawdown"].max(),
               "max_drawdown_gross": daily["gross_drawdown"].max(),
               "peak_gross_exposure": daily["gross_exposure"].max(),
               "peak_abs_net_exposure": daily["net_exposure"].abs().max()}
    for direction, sign in [("long", 1), ("short", -1)]:
        summary.update({f"{direction}_outside_days": int(signals[f"outside_{direction}"].sum()),
                        f"{direction}_crossings": int(signals[f"{direction}_crossing"].sum()),
                        f"{direction}_signals": int(signals[f"eligible_{direction}"].sum()),
                        f"{direction}_executed_entries": int(trades["direction"].eq(sign).sum()),
                        f"{direction}_closed_trades": int(closed["direction"].eq(sign).sum())})
    summary["unfilled_orders"] = int(signals["order_status"].eq("unfilled_end_of_period").sum())
    summary["exit_signals"] = int(signals["exit_signal"].sum())
    summary["ignored_crossings"] = int(signals["ignored_reason"].ne("").sum())
    return summary


def simulate(prices, zscores, beta, *, capital=10000., cost_rate=.0005, previous_z=None,
             decision=decide_signal, entry_threshold=2., exit_threshold=0.):
    """Return signals, fills, trades, daily accounts, and a per-account summary.

    The injected decision function sees the previous/current Z-score and current
    position after that session's fill; it cannot see future prices.
    """
    if (prices.empty or not prices.index.equals(zscores.index) or prices.index.has_duplicates
            or not isinstance(prices.index, pd.DatetimeIndex) or prices.index.hasnans
            or not prices.index.is_monotonic_increasing
            or not np.isfinite(prices[PRICE_COLUMNS].to_numpy(dtype=float)).all()
            or (prices[PRICE_COLUMNS] <= 0).any().any() or not np.isfinite(zscores).all()
            or not np.isfinite([beta, capital, cost_rate]).all()
            or beta <= 0 or capital <= 0 or cost_rate < 0):
        raise ValueError("Invalid or misaligned backtest prices, Z-scores, beta, or capital")
    cash, cumulative_costs = float(capital), 0.
    q = np.zeros(2)
    pending = active = None
    signals, executions, trades, daily = [], [], [], []
    previous_close = None
    previous_equity = previous_gross_equity = net_peak = gross_peak = float(capital)
    status = "complete"
    next_id = 0
    for i, (timestamp, row) in enumerate(prices.iterrows()):
        date = str(timestamp.date())
        opens = row[["dependent_Open", "independent_Open"]].to_numpy(dtype=float)
        closes = row[["dependent_Close", "independent_Close"]].to_numpy(dtype=float)
        leg_pnl = q * (opens - previous_close) if previous_close is not None else np.zeros(2)
        fill_id = ""
        if pending is not None:
            action = pending["action"]
            signal = signals[pending["signal_index"]]
            if action.startswith("enter"):
                direction = 1 if action == "enter_long" else -1
                q_new = entry_quantities(capital, cash, cost_rate, beta, opens, direction)
                next_id += 1
                active = {"trade_id": f"T{next_id:04d}", "direction": direction, "q": q_new.copy(),
                          "prices": opens.copy(), "date": date, "index": i,
                          "signal_date": signal["Date"], "gross": float(np.abs(q_new) @ opens), "costs": 0.}
            else:
                q_new = np.zeros(2)
            fill_id = active["trade_id"]
            delta = q_new - q
            fill_costs = cost_rate * np.abs(delta) * opens
            cash -= float(delta @ opens + fill_costs.sum())
            cumulative_costs += float(fill_costs.sum())
            active["costs"] += float(fill_costs.sum())
            for leg, dq, price, cost in zip(("dependent", "independent"), delta, opens, fill_costs):
                executions.append({"Date": date, "signal_date": signal["Date"], "trade_id": fill_id,
                                   "action": action, "leg": leg, "shares_change": dq, "price": price,
                                   "turnover": abs(dq) * price, "cost": cost})
            signal.update(order_status="filled", execution_date=date, trade_id=fill_id)
            q = q_new
            if action == "exit":
                trades.append(_trade_record(active, opens, date, i, signal["Date"], closed=True))
                active = None
            pending = None
        leg_pnl += q * (closes - opens)
        net_equity = cash + float(q @ closes)
        gross_equity = net_equity + cumulative_costs
        net_peak, gross_peak = max(net_peak, net_equity), max(gross_peak, gross_equity)
        daily.append({"Date": date, "trade_id": active["trade_id"] if active else "", "fill_trade_id": fill_id,
                      "position": active["direction"] if active else 0,
                      "q_dependent": q[0], "q_independent": q[1], "cash": cash,
                      "dependent_exposure": q[0] * closes[0], "independent_exposure": q[1] * closes[1],
                      "net_exposure": float(q @ closes), "gross_exposure": float(np.abs(q) @ closes),
                      "dependent_pnl": leg_pnl[0], "independent_pnl": leg_pnl[1],
                      "net_pnl": net_equity - previous_equity,
                      "gross_pnl": gross_equity - previous_gross_equity,
                      "cumulative_costs": cumulative_costs, "net_equity": net_equity, "gross_equity": gross_equity,
                      "net_drawdown": 1 - net_equity / net_peak,
                      "gross_drawdown": 1 - gross_equity / gross_peak})
        position = active["direction"] if active else 0
        d = decision(previous_z, float(zscores.iloc[i]), position, entry_threshold, exit_threshold)
        signal_row = {"Date": date, "previous_z": previous_z, "zscore": zscores.iloc[i],
                      "position": position, **d, "order_status": "none", "execution_date": "",
                      "trade_id": active["trade_id"] if active else ""}
        if net_equity <= 0:
            status = "incomplete_nonpositive_equity"
            signal_row["order_status"] = "stopped_nonpositive_equity"
        elif d["action"] != "hold":
            signal_row["order_status"] = "unfilled_end_of_period"
            pending = {"action": d["action"], "signal_index": len(signals)}
        signals.append(signal_row)
        previous_close, previous_z = closes, float(zscores.iloc[i])
        previous_equity, previous_gross_equity = net_equity, gross_equity
        if status != "complete":
            break
    if active:
        trades.append(_trade_record(active, closes, date, i))
    tables = {"signals": pd.DataFrame(signals),
              "executions": pd.DataFrame(executions, columns=EXECUTION_COLUMNS),
              "trades": pd.DataFrame(trades, columns=TRADE_COLUMNS), "daily_account": pd.DataFrame(daily)}
    tables["summary"] = summarize(tables, capital, status)
    return tables
