"""Checks for direction selection, test interpretation, and the historical boundary."""

import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import CollinearityWarning

from market_analytics.cointegration.selection import (
    adjust_pair_pvalues, analyse, directional_test, half_life, load_config,
    rank_pairs, read_input, reconstruct_spread, select_levels_lag,
    sequential_rank, stock_pairs, validate_input,
)
from market_analytics.data.master import STOCKS, sha256


ROOT = Path(__file__).resolve().parents[1]


def config():
    return json.loads((ROOT / "configs/pair_selection.json").read_text())


def sample():
    rng = np.random.default_rng(17)
    dates = pd.bdate_range("2018-01-02", periods=75).append(pd.bdate_range("2022-01-03", periods=75))
    frame = pd.DataFrame({f"{symbol}_Close": np.exp(4 + np.cumsum(rng.normal(0, .01, len(dates))))
                          for symbol in STOCKS}, index=dates)
    cfg = config()
    cfg["period"].update(rows=len(dates), first_session=str(dates[0].date()), last_session=str(dates[-1].date()))
    return frame, cfg


class SelectionTests(unittest.TestCase):
    def test_pairs_and_directional_identity(self):
        pairs = stock_pairs(STOCKS)
        self.assertEqual(len(pairs), 15)
        self.assertEqual(pairs[0], ("MSFT", "GOOGL"))
        self.assertEqual(pairs[-1], ("AMZN", "META"))
        frame, cfg = sample()
        logs = np.log(frame).set_axis(STOCKS, axis=1)
        row, residual = directional_test(logs, "MSFT", "GOOGL", cfg)
        reverse, _ = directional_test(logs, "GOOGL", "MSFT", cfg)
        self.assertEqual(row["pair_id"], reverse["pair_id"])
        self.assertEqual(row["spread_column"], "MSFT_on_GOOGL")
        coefficients = np.linalg.lstsq(np.column_stack([np.ones(len(logs)), logs.GOOGL]), logs.MSFT, rcond=None)[0]
        np.testing.assert_allclose([row["intercept"], row["beta"]], coefficients, atol=1e-10)
        np.testing.assert_allclose(reconstruct_spread(frame, row), residual, atol=1e-10)

    def test_pair_adjustment_matches_hand_calculation(self):
        pair_p, adjusted = adjust_pair_pvalues([.001, .02, .6] + [.4]*12,
                                               [.01, .03, .8] + [.7]*12, .05)
        np.testing.assert_allclose(pair_p[:3], [.002, .04, 1.0])
        self.assertAlmostEqual(adjusted[0], .03)
        self.assertAlmostEqual(adjusted[1], .56)
        self.assertAlmostEqual(adjusted[2], 1.0)

    def test_sequential_rank_stops_and_equality_does_not_reject(self):
        self.assertEqual(sequential_rank([5, 100], [10, 3]), 0)
        self.assertEqual(sequential_rank([11, 3], [10, 3]), 1)
        self.assertEqual(sequential_rank([11, 4], [10, 3]), 2)
        self.assertEqual(sequential_rank([10, 4], [10, 3]), 0)

    def test_lag_zero_is_ineligible_and_tie_uses_smaller_order(self):
        self.assertEqual(select_levels_lag([-100, 4, 2, 2, 6]), 2)

    def test_agreement_precedes_pvalue_and_support_is_separate(self):
        cfg = config()
        directions, johansen = [], []
        for order, (a, b) in enumerate(stock_pairs(STOCKS)):
            for d, (y, x) in enumerate([(a, b), (b, a)]):
                directions.append({"pair_id": f"{a}_{b}", "dependent": y, "independent": x,
                                   "direction_order": d, "eg_pvalue": (.0001 if order == 0 else .01 if order == 1 else .5) + d*.001})
            johansen.append({"pair_id": f"{a}_{b}", "trace_rank_95": 1 if order == 1 else 0,
                             "max_eig_rank_95": 0})
        integration = pd.DataFrame([{"symbol": s, "i1_status": "consistent_with_i1"} for s in STOCKS])
        ranked = rank_pairs(pd.DataFrame(directions), pd.DataFrame(johansen), integration, cfg)
        self.assertEqual(ranked.iloc[0].pair_id, "MSFT_NVDA")
        self.assertEqual(ranked.iloc[1].pair_id, "MSFT_GOOGL")
        self.assertEqual(ranked.iloc[0].evidence_label, "exploratory")
        self.assertEqual(ranked.iloc[0].method_agreement, "both")
        # Rank two must not count as the intended Johansen rank-one evidence.
        johansen[1]["trace_rank_95"] = 2
        ranked = rank_pairs(pd.DataFrame(directions), pd.DataFrame(johansen), integration, cfg)
        self.assertFalse(ranked.loc[ranked.pair_id == "MSFT_NVDA", "johansen_reject"].item())

    def test_direction_ties_follow_canonical_order(self):
        cfg = config()
        directions, johansen = [], []
        for a, b in stock_pairs(STOCKS):
            for d, (y, x) in enumerate([(a,b),(b,a)]):
                directions.append({"pair_id": f"{a}_{b}", "dependent": y, "independent": x,
                                   "direction_order": d, "eg_pvalue": .5})
            johansen.append({"pair_id": f"{a}_{b}", "trace_rank_95": 0, "max_eig_rank_95": 0})
        integration = pd.DataFrame([{"symbol": s, "i1_status": "consistent_with_i1"} for s in STOCKS])
        ranked = rank_pairs(pd.DataFrame(directions).iloc[::-1], pd.DataFrame(johansen), integration, cfg)
        self.assertEqual(ranked.iloc[0].pair_id, "MSFT_GOOGL")
        self.assertEqual(ranked.iloc[0].dependent, "MSFT")

    def test_half_life_known_coefficient_and_non_reversion(self):
        dates = pd.bdate_range("2020-01-01", periods=15)
        result = half_life(pd.Series(.5 ** np.arange(15), index=dates))
        self.assertAlmostEqual(result["half_life_sessions"], 1.0)
        result = half_life(pd.Series(1.1 ** np.arange(15), index=dates))
        self.assertEqual(result["status"], "non_mean_reverting")
        self.assertTrue(np.isnan(result["half_life_sessions"]))
        result = half_life(pd.Series([1.] + [0.]*14, index=dates))
        self.assertEqual(result["status"], "nonpositive_phi")
        self.assertTrue(np.isnan(result["half_life_sessions"]))

    def test_config_cannot_silently_change_implemented_selection_rules(self):
        cfg = config()
        cfg["multiplicity"]["direction_multiplier"] = 1
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "configs/pair_selection.json"
            path.parent.mkdir()
            path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_bad_prices_and_unseen_dates_stop(self):
        frame, cfg = sample()
        for value in [0, -1, np.nan, np.inf]:
            bad = frame.copy()
            bad.iloc[5, 0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_input(bad, cfg)
        bad = frame.copy()
        bad.index = pd.bdate_range("2026-01-02", periods=len(bad))
        with self.assertRaisesRegex(ValueError, "historical|2026"):
            validate_input(bad, cfg)

    def test_collinearity_and_nonfinite_statistic_stop(self):
        frame, cfg = sample()
        logs = np.log(frame).set_axis(STOCKS, axis=1)
        def warn(*args, **kwargs):
            warnings.warn("near collinear", CollinearityWarning)
        with patch("market_analytics.cointegration.selection.coint", side_effect=warn):
            with self.assertRaises(ValueError):
                directional_test(logs, "MSFT", "GOOGL", cfg)
        with patch("market_analytics.cointegration.selection.coint", return_value=(-np.inf, 0., [-4, -3, -2])):
            with self.assertRaises(ValueError):
                directional_test(logs, "MSFT", "GOOGL", cfg)
        logs["MSFT"] = 2 + 3*logs.GOOGL
        with self.assertRaises(ValueError):
            directional_test(logs, "MSFT", "GOOGL", cfg)

    def test_residual_statistic_matches_but_ordinary_adf_pvalue_is_not_exported(self):
        frame, cfg = sample()
        row, _ = directional_test(np.log(frame).set_axis(STOCKS, axis=1), "MSFT", "GOOGL", cfg)
        self.assertAlmostEqual(row["eg_statistic"], row["residual_adf_statistic"], places=8)
        self.assertEqual(row["residual_regression"], "n")
        self.assertNotIn("residual_adf_pvalue", row)

    def test_historical_only_read_hash_check_and_output_counts(self):
        frame, cfg = sample()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / cfg["input"]
            path.parent.mkdir(parents=True)
            frame.rename_axis("Date").to_csv(path)
            manifest = root / cfg["manifest"]
            manifest.write_text(json.dumps({"outputs": {cfg["input"]: sha256(path), "unseen_must_not_be_opened.csv": "unused"}}))
            read, _ = read_input(root, cfg)
            tables, spreads, checks, _ = analyse(read, cfg)
            self.assertEqual(len(tables["directional_tests"]), 30)
            self.assertEqual(len(tables["integration_tests"]), 12)
            self.assertEqual(len(tables["johansen_tests"]), 15)
            self.assertEqual(len(tables["lag_selection"]), 165)
            self.assertEqual(len(tables["hedge_stability"]), 30)
            self.assertEqual(spreads.shape, (len(frame), 15))
            self.assertTrue(all(c["status"] == "pass" for c in checks))
            path.write_text(path.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "hash|manifest"):
                read_input(root, cfg)


if __name__ == "__main__":
    unittest.main()
