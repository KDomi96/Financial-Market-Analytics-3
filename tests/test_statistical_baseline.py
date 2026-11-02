"""Known normalization, timing, and two-leg cash calculations for Phase 4."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from market_analytics.trading.baseline import (
    apply_normalization, fit_normalization, load_config, read_handoff,
    run_statistical_baseline, validate_prices,
)
from market_analytics.trading.backtest import entry_quantities, share_quantities, simulate
from market_analytics.trading.signals import decide_signal
from market_analytics.data.master import sha256


ROOT = Path(__file__).resolve().parents[1]


def prices(z=(-2, -3, 0, 0)):
    dates = pd.to_datetime(["2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"])
    frame = pd.DataFrame({"dependent_Open": [10, 10, 10, 11],
                          "independent_Open": [20, 20, 20, 18],
                          "dependent_Close": [10, 10, 10.5, 11],
                          "independent_Close": [20, 20, 19, 18]}, index=dates)
    return frame, pd.Series(z, index=dates, dtype=float)


def handoff_fixture(root):
    cfg = json.loads((ROOT / "configs/statistical_baseline.json").read_text())
    dates = pd.bdate_range("2018-01-02", "2025-12-31")
    dates = dates[np.linspace(0, len(dates) - 1, 2011).astype(int)]
    x = np.arange(len(dates))
    frame = pd.DataFrame({f"{s}_{field}": np.exp(4 + .0001 * x + .02 * np.sin(x / period))
                          for s, period in [("AMZN", 17), ("META", 23), ("NVDA", 31)]
                          for field in ("Open", "Close")}, index=dates)
    frame.index.name = "Date"
    def save(relative, value):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, pd.DataFrame):
            value.to_csv(path, index="Date" in value.index.names, lineterminator="\n")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")
        return sha256(path)
    historical_hash = save(cfg["historical"], frame)
    save(cfg["manifest"], {"outputs": {cfg["historical"]: historical_hash}})
    output_hashes = {cfg["shortlist"]: save(cfg["shortlist"], pd.DataFrame(cfg["pairs"]))}
    spreads = pd.DataFrame(index=dates)
    for pair in cfg["pairs"]:
        p = {**pair, "model_version": "phase3_v1", "shortlisted": True, "fit_start": "2018-01-02",
             "fit_end": "2025-12-31", "nobs": 2011, "input_sha256": historical_hash,
             "settings_sha256": "synthetic_settings", "intercept": .5, "beta": .6,
             "transformation": "natural log of Yahoo Close; dividends excluded",
             "spread_formula": "log(dependent_Close) - intercept - beta * log(independent_Close)"}
        relative = f"{cfg['ols_directory']}/{pair['pair_id']}/ols_20180102_20251231.json"
        output_hashes[relative] = save(relative, p)
        spreads[pair["spread_column"]] = np.log(frame[pair["dependent"] + "_Close"]) - .5 - .6 * np.log(frame[pair["independent"] + "_Close"])
    spreads.index.name = "Date"
    output_hashes[cfg["historical_spreads"]] = save(cfg["historical_spreads"], spreads)
    save(cfg["phase3_metadata"], {"input": {"sha256": historical_hash}, "settings": {"sha256": "synthetic_settings"}, "outputs": output_hashes})
    (root / "configs").mkdir(exist_ok=True)
    (root / "configs/statistical_baseline.json").write_text(json.dumps(cfg))
    (root / "scripts").mkdir()
    (root / "scripts/run_statistical_baseline.py").write_text("# Synthetic runner for code hashing\n")
    return cfg


class BaselineTests(unittest.TestCase):
    def test_normalization_is_2025_sample_std_and_reloadable(self):
        s = pd.Series([1., 2., 3.], index=pd.date_range("2025-01-02", periods=3))
        fitted = json.loads(json.dumps(fit_normalization(s)))
        self.assertEqual((fitted["mean"], fitted["std"], fitted["ddof"]), (2, 1, 1))
        self.assertEqual(apply_normalization(pd.Series([4.]), fitted).iloc[0], 2)
        for bad in (s * 0, s.iloc[:1], s * np.nan,
                    pd.Series([1., 2.], index=pd.to_datetime(["2025-12-31", "2026-01-02"]))):
            with self.assertRaises(ValueError):
                fit_normalization(bad)

    def test_exact_thresholds_repetitions_and_exit_priority(self):
        self.assertEqual(decide_signal(0, -2, 0)["action"], "hold")
        self.assertEqual(decide_signal(-2, -3, 0)["action"], "enter_long")
        self.assertEqual(decide_signal(2, 3, 0)["action"], "enter_short")
        self.assertEqual(decide_signal(-3, -4, 0)["action"], "hold")
        decision = decide_signal(-3, 3, 1)
        self.assertEqual(decision["action"], "exit")
        self.assertTrue(decision["short_crossing"])
        self.assertFalse(decision["eligible_short"])
        self.assertEqual(decide_signal(3, 0, -1)["action"], "exit")

    def test_hand_computed_long_and_short_cash_pnl(self):
        np.testing.assert_allclose(share_quantities(100, .5, [10, 20], 1), [10, -2.5])
        frame, z = prices()
        capital = 150 * 1.0005
        result = simulate(frame, z, .5, capital=capital)
        trade = result["trades"].iloc[0]
        for key, expected in {"gross_pnl": 15, "costs": .1525, "net_pnl": 14.8475,
                              "dependent_pnl": 10, "independent_pnl": 5}.items():
            self.assertAlmostEqual(trade[key], expected)
        self.assertEqual(result["executions"]["Date"].tolist(),
                         ["2025-01-07", "2025-01-07", "2025-01-08", "2025-01-08"])
        short = simulate(frame, -z, .5, capital=capital)
        self.assertAlmostEqual(short["trades"].iloc[0]["gross_pnl"], -15)
        self.assertAlmostEqual(short["trades"].iloc[0]["net_pnl"], -15.1525)
        self.assertEqual(trade["holding_sessions"], 1)

    def test_sizing_reserves_costs_and_does_not_reinvest_gains(self):
        for equity, expected in [(10000, 10000), (12000, 10000), (9000, 9000)]:
            q = entry_quantities(10000, equity, .0005, .5, [10, 20], 1)
            turnover = np.abs(q) @ [10, 20]
            self.assertAlmostEqual(turnover * 1.0005, expected)

    def test_first_context_last_signal_open_trade_and_empty_metrics(self):
        frame, z = prices((-3, -3, -3, -3))
        none = simulate(frame, z, .5, previous_z=-3)
        self.assertEqual(none["summary"]["executed_entries"], 0)
        self.assertTrue(pd.isna(none["summary"]["win_rate"]))
        self.assertEqual(none["summary"]["net_return"], 0)
        opened = simulate(frame, z, .5, previous_z=0)
        self.assertEqual(opened["summary"]["open_trades"], 1)
        self.assertTrue(pd.isna(opened["summary"]["win_rate"]))
        self.assertEqual(len(opened["executions"]), 2)
        final = simulate(frame, pd.Series([0, 0, 0, -3.], index=z.index), .5)
        self.assertEqual(final["summary"]["long_signals"], 1)
        self.assertEqual(final["summary"]["executed_entries"], 0)
        self.assertEqual(final["signals"].iloc[-1]["order_status"], "unfilled_end_of_period")

    def test_future_prices_do_not_change_prior_decisions_and_gaps_are_retained(self):
        frame, z = prices()
        first = simulate(frame, z, .5)
        changed = frame.copy()
        changed.iloc[2, 0] = 15
        second = simulate(changed, z, .5)
        pd.testing.assert_frame_equal(first["signals"].iloc[:2], second["signals"].iloc[:2])
        self.assertNotEqual(first["trades"].iloc[0]["q_dependent"], second["trades"].iloc[0]["q_dependent"])
        changed.iloc[-1, 2] = 500
        third = simulate(changed, z, .5)
        pd.testing.assert_frame_equal(second["executions"], third["executions"])

    def test_opposite_entry_is_not_queued_after_exit(self):
        frame, z = prices((-2, -3, 3, 3))
        result = simulate(frame, z, .5)
        self.assertEqual(result["summary"]["executed_entries"], 1)
        self.assertEqual(result["summary"]["short_signals"], 0)

    def test_equity_rebuilt_from_fills_and_source_prices(self):
        frame, z = prices()
        result = simulate(frame, z, .5)
        shares = np.zeros(2)
        wealth = 10000.
        last_close = None
        for i, (date, row) in enumerate(frame.iterrows()):
            opens = row.iloc[:2].to_numpy()
            closes = row.iloc[2:].to_numpy()
            if last_close is not None:
                wealth += float(shares @ (opens - last_close))
            fills = result["executions"].loc[lambda x: x["Date"].eq(str(date.date()))]
            for fill in fills.itertuples():
                leg = 0 if fill.leg == "dependent" else 1
                shares[leg] += fill.shares_change
                wealth -= fill.cost
            wealth += float(shares @ (closes - opens))
            self.assertAlmostEqual(wealth, result["daily_account"].iloc[i]["net_equity"])
            last_close = closes

    def test_initial_drawdown_and_insolvency(self):
        frame, z = prices((-3, -3, -3, -3))
        frame.iloc[1, 2] = .01
        frame.iloc[1, 3] = 100
        result = simulate(frame, z, .5, previous_z=0)
        self.assertEqual(result["summary"]["status"], "incomplete_nonpositive_equity")
        self.assertEqual(len(result["daily_account"]), 2)
        frame, z = prices()
        frame.iloc[2, 2:4] = [10, 20]
        normal = simulate(frame, z, .5)
        self.assertGreater(normal["summary"]["max_drawdown_net"], 0)

    def test_price_dates_values_and_alignment_are_rejected(self):
        frame, _ = prices()
        spec = {"start": "2025-01-01", "end": "2025-12-31", "first_session": "2025-01-03",
                "last_session": "2025-01-08", "rows": 4}
        validate_prices(frame, spec)
        for bad in (frame.iloc[:-1], frame.iloc[[0, 1, 1, 3]], frame.assign(dependent_Open=0)):
            with self.assertRaises(ValueError):
                validate_prices(bad, spec)

    def test_historical_runner_does_not_open_unseen_and_handoff_is_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cfg = handoff_fixture(temp_root)
            self.assertEqual(len(read_handoff(temp_root, cfg)["parameters"]), 2)
            actual_read = Path.read_bytes
            def guarded_read(path):
                if str(path).endswith("master_unseen.csv"):
                    raise AssertionError("historical run opened unseen")
                return actual_read(path)
            with patch.object(Path, "read_bytes", guarded_read):
                metadata = run_statistical_baseline(temp_root / "configs/statistical_baseline.json", historical_only=True, figures=False)
            self.assertEqual(set(metadata), {"historical"})
            bad = json.loads(json.dumps(cfg))
            bad["pairs"][0]["dependent"] = "META"
            with self.assertRaises(ValueError):
                read_handoff(temp_root, bad)
            with patch("market_analytics.trading.baseline.sha256", return_value="bad"):
                with self.assertRaises(ValueError):
                    read_handoff(temp_root, cfg)

    def test_evaluation_loads_saved_normalization_and_preserves_changed_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = handoff_fixture(root)
            config_path = root / "configs/statistical_baseline.json"
            run_statistical_baseline(config_path, historical_only=True, figures=False)
            dates = pd.bdate_range("2026-01-02", "2026-07-31")
            dates = dates[np.linspace(0, len(dates) - 1, 145).astype(int)]
            frame = pd.DataFrame({f"{s}_{field}": np.exp(4 + .01 * np.sin(np.arange(145) / k))
                                  for s, k in [("AMZN", 17), ("META", 23), ("NVDA", 31)]
                                  for field in ("Open", "Close")}, index=dates)
            frame.index.name = "Date"
            unseen_path = root / cfg["unseen"]
            frame.to_csv(unseen_path)
            manifest_path = root / cfg["manifest"]
            manifest = json.loads(manifest_path.read_text())
            manifest["outputs"][cfg["unseen"]] = sha256(unseen_path)
            manifest_path.write_text(json.dumps(manifest))
            with patch("market_analytics.trading.baseline.fit_normalization", side_effect=AssertionError("evaluation refitted")):
                run_statistical_baseline(config_path, figures=False)
            meta = root / cfg["outputs"]["metrics"] / "unseen/run_metadata.json"
            previous_hash = sha256(meta)
            frame.iloc[0, 0] *= 1.01
            frame.to_csv(unseen_path)
            manifest["outputs"][cfg["unseen"]] = sha256(unseen_path)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                run_statistical_baseline(config_path, figures=False)
            self.assertEqual(sha256(meta), previous_hash)
            contract = root / cfg["outputs"]["metrics"] / "evaluation_contract.json"
            saved = contract.read_text()
            contract.unlink()
            with self.assertRaises(ValueError):
                run_statistical_baseline(config_path, historical_only=True, figures=False)
            contract.write_text(saved)
            artifact = root / cfg["outputs"]["artifacts"] / "AMZN_META/normalization_2025.json"
            artifact.write_text("{}")
            with self.assertRaises(ValueError):
                run_statistical_baseline(config_path, historical_only=True, figures=False)


if __name__ == "__main__":
    unittest.main()
