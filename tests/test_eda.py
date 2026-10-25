"""Small examples for the EDA calculations that could go wrong without an error."""

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from market_analytics.analysis.eda import (
    INCOMPLETE, OK, ZERO_VARIANCE, analyse, assign_vix_groups, compounded_pct, correlation,
    max_drawdown, read_input, regression, return_summaries, rolling_correlations,
    split_input, stock_pairs, validate_input, vix_boundaries,
)
from market_analytics.data.master import STOCKS


def config(dates, window=5) -> dict:
    return {
        "input": "data/processed/master_historical.csv", "manifest": "data/processed/master_manifest.json",
        "period": {"start": "2018-01-01", "end": "2025-12-31", "first_session": str(dates[0].date()),
                   "last_session": str(dates[-1].date()), "rows": len(dates)},
        "stocks": list(STOCKS), "benchmark": "GSPC", "annualization_days": 252,
        "rolling_window": window, "min_observations": 3, "vix_groups": ["low", "medium", "high"],
        "vix_quantile_method": "linear", "outputs": {"metrics": "out", "figures": "fig"},
    }


def master(dates=None, seed=0) -> pd.DataFrame:
    """A small historical master with random but valid prices."""
    dates = pd.bdate_range("2024-12-02", "2025-01-31") if dates is None else dates
    rng = np.random.default_rng(seed)
    columns = {}
    for symbol in list(STOCKS) + ["GSPC"]:
        returns = rng.normal(0, 1.5, len(dates))
        returns[0] = np.nan
        close = 100 * np.cumprod(1 + np.nan_to_num(returns) / 100)
        columns[f"{symbol}_Close"], columns[f"{symbol}_Return"] = close, returns
    columns["VIX_Close"] = rng.uniform(12, 35, len(dates)).round(2)
    return pd.DataFrame(columns, index=pd.DatetimeIndex(dates, name="Date"))


class ReturnAndRiskTests(unittest.TestCase):
    def test_compounding_is_not_additive(self):
        self.assertAlmostEqual(compounded_pct(pd.Series([10.0, -10.0])), -1.0, places=12)

    def test_drawdown_counts_the_starting_value_and_first_session(self):
        dates = pd.bdate_range("2025-01-02", periods=3)
        value, peak, trough = max_drawdown(pd.Series([-10.0, 5.0, 2.0], index=dates),
                                           pd.Timestamp("2024-12-31"))
        self.assertAlmostEqual(value, -10.0, places=12)
        self.assertEqual((peak, trough), ("2024-12-31", "2025-01-02"))

    def test_annual_window_starts_from_previous_years_close(self):
        frame = master()
        cfg = config(frame.index)
        closes, returns, _ = split_input(frame, cfg)
        _, annual, _ = return_summaries(closes, returns, cfg)
        row = annual[(annual["instrument"] == "MSFT") & (annual["year"] == 2025)].iloc[0]
        self.assertEqual(row["first_date"], "2025-01-01")
        self.assertEqual(row["base_date"], "2024-12-31")
        ratio = 100 * (closes["MSFT"].iloc[-1] / closes.loc["2024-12-31", "MSFT"] - 1)
        self.assertAlmostEqual(row["compounded_return_pct"], ratio, places=9)
        expected_std = np.std(returns.loc[returns.index.year == 2025, "MSFT"], ddof=1)
        self.assertAlmostEqual(row["annualized_vol_pct"], expected_std * math.sqrt(252), places=12)


class PairTests(unittest.TestCase):
    def test_fifteen_unordered_pairs_in_display_order(self):
        pairs = stock_pairs(STOCKS)
        self.assertEqual(len(pairs), 15)
        self.assertEqual(len({frozenset(pair) for pair in pairs}), 15)
        self.assertEqual((pairs[0], pairs[-1]), (("MSFT", "GOOGL"), ("AMZN", "META")))

    def test_correlation_extremes_and_constant_samples(self):
        x = pd.Series([1.0, -2.0, 0.5, 3.0])
        self.assertAlmostEqual(correlation(x, x, 3)[0], 1.0, places=12)
        self.assertAlmostEqual(correlation(x, -x, 3)[0], -1.0, places=12)
        value, status = correlation(x, pd.Series([0.1] * 4), 3)
        self.assertTrue(math.isnan(value))
        self.assertEqual(status, ZERO_VARIANCE)

    def test_matrix_matches_pair_table(self):
        tables, _, _ = analyse(master(), config(master().index))
        matrix, pairs = tables["return_correlation_matrix"], tables["pair_correlations"]
        for row in pairs.itertuples():
            self.assertEqual(matrix.loc[row.stock_a, row.stock_b], row.return_correlation)
            self.assertEqual(matrix.loc[row.stock_b, row.stock_a], row.return_correlation)

    def test_constant_stock_keeps_undefined_correlations_through_full_analysis(self):
        frame = master()
        frame.loc[:, "MSFT_Close"] = 100.0
        frame.loc[frame.index[1:], "MSFT_Return"] = 0.0
        tables, _, _ = analyse(frame, config(frame.index))
        matrix = tables["return_correlation_matrix"]
        self.assertTrue(matrix.loc["MSFT"].isna().all())
        self.assertTrue(matrix["MSFT"].isna().all())
        self.assertEqual(matrix.loc["GOOGL", "GOOGL"], 1.0)
        pd.testing.assert_frame_equal(matrix, matrix.T, check_names=False)
        pairs = tables["pair_correlations"]
        affected = pairs["stock_a"].eq("MSFT") | pairs["stock_b"].eq("MSFT")
        self.assertTrue(pairs.loc[affected, "return_status"].eq(ZERO_VARIANCE).all())
        self.assertTrue(pairs.loc[affected, "return_correlation"].isna().all())


class BenchmarkTests(unittest.TestCase):
    def test_exact_linear_relation(self):
        x = pd.Series([0.5, -1.2, 2.0, 0.3, -0.7])
        row = regression(0.1 + 2 * x, x, {"min_observations": 3})
        self.assertAlmostEqual(row["alpha_pct"], 0.1, places=10)
        self.assertAlmostEqual(row["beta"], 2.0, places=10)
        self.assertAlmostEqual(row["r_squared"], 1.0, places=10)

    def test_constant_benchmark_has_no_estimate(self):
        row = regression(pd.Series([0.5, -1.0, 2.0, 0.3]), pd.Series([0.7] * 4), {"min_observations": 3})
        self.assertEqual(row["status"], ZERO_VARIANCE)
        self.assertNotIn("beta", row)


class RollingTests(unittest.TestCase):
    def setUp(self):
        self.frame = master()
        self.cfg = config(self.frame.index)
        _, self.returns, _ = split_input(self.frame, self.cfg)

    def test_windows_start_after_enough_observations(self):
        table, _ = rolling_correlations(self.returns, self.cfg)
        first = table[table["pair"] == "MSFT_GOOGL"]
        self.assertTrue((first["status"].iloc[:4] == INCOMPLETE).all())
        self.assertTrue(first["correlation"].iloc[:4].isna().all())
        self.assertEqual(first["status"].iloc[4], OK)

    def test_later_observation_cannot_change_earlier_window(self):
        before, _ = rolling_correlations(self.returns, self.cfg)
        changed = self.returns.copy()
        changed.iloc[20:, changed.columns.get_loc("MSFT")] += 5
        after, _ = rolling_correlations(changed, self.cfg)
        cut = self.returns.index[19].strftime("%Y-%m-%d")
        early = before["date"] <= cut
        pd.testing.assert_series_equal(before.loc[early, "correlation"], after.loc[early, "correlation"])

    def test_constant_window_is_missing_not_infinite(self):
        returns = self.returns.copy()
        returns.iloc[5:10, returns.columns.get_loc("MSFT")] = 0.3
        table, _ = rolling_correlations(returns, self.cfg)
        row = table[(table["pair"] == "MSFT_GOOGL") & (table["date"] == returns.index[9].strftime("%Y-%m-%d"))]
        self.assertEqual(row["status"].item(), ZERO_VARIANCE)
        self.assertTrue(math.isnan(row["correlation"].item()))

    def test_history_shorter_than_window_remains_incomplete(self):
        frame = master(pd.bdate_range("2025-01-02", periods=4))
        tables, _, _ = analyse(frame, config(frame.index, window=60))
        rolling = tables["rolling_correlations"]
        self.assertEqual(len(rolling), 3 * 15)
        self.assertTrue(rolling["status"].eq(INCOMPLETE).all())
        self.assertTrue(rolling["correlation"].isna().all())
        self.assertEqual(rolling.loc[rolling["pair"].eq("MSFT_GOOGL"), "n"].tolist(), [1, 2, 3])


class VixGroupTests(unittest.TestCase):
    def test_boundary_values_and_ties_join_the_lower_group(self):
        dates = pd.bdate_range("2025-01-02", periods=7)
        vix = pd.Series([10.0, 20.0, 20.0, 20.0, 30.0, 40.0, 50.0], index=dates)
        cfg = {"vix_groups": ["low", "medium", "high"], "vix_quantile_method": "linear"}
        boundaries = vix_boundaries(vix, dates, cfg)
        self.assertEqual(boundaries["boundaries"], [20.0, 30.0])
        groups = assign_vix_groups(vix, boundaries)
        self.assertEqual(groups.tolist(), ["low"] * 4 + ["medium", "high", "high"])

    def test_first_date_excluded_and_every_return_date_grouped_once(self):
        frame = master()
        cfg = config(frame.index)
        tables, boundaries, _ = analyse(frame, cfg)
        self.assertEqual(boundaries["estimation_first_date"], str(frame.index[1].date()))
        self.assertEqual(boundaries["estimation_n"], len(frame) - 1)
        self.assertEqual(tables["vix_group_year_counts"]["n"].sum(), len(frame) - 1)


class IsolationTests(unittest.TestCase):
    def test_unseen_row_is_rejected(self):
        frame = master(pd.bdate_range("2025-12-01", "2026-01-09"))
        cfg = config(frame.index)
        cfg["period"]["last_session"] = "2025-12-31"
        with self.assertRaisesRegex(ValueError, "outside the historical period"):
            validate_input(frame, cfg)

    def test_unexpected_missing_return_stops_the_run(self):
        frame = master()
        frame.iloc[10, frame.columns.get_loc("AAPL_Return")] = np.nan
        with self.assertRaisesRegex(ValueError, "missing or non-finite"):
            validate_input(frame, config(frame.index))

    def test_runs_with_only_the_historical_master_and_manifest(self):
        frame = master()
        cfg = config(frame.index)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / cfg["input"]
            path.parent.mkdir(parents=True)
            frame.to_csv(path, lineterminator="\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / cfg["manifest"]).write_text(json.dumps({"outputs": {cfg["input"]: digest}}))
            loaded, input_hash = read_input(root, cfg)
            self.assertEqual(input_hash, digest)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()),
                             ["master_historical.csv", "master_manifest.json"])
            analyse(loaded, cfg)
            path.write_text(path.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "manifest hash"):
                read_input(root, cfg)


if __name__ == "__main__":
    unittest.main()
