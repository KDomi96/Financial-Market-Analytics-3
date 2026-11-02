"""Synthetic checks for the single-pair verdict, fit windows, and signals."""

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from market_analytics.api.analysis import (
    analyse_pair, decide, fit_window_normalization, split_sessions, walk_signals,
)
from market_analytics.api.prices import InputError

ROOT = Path(__file__).resolve().parents[1]
PAIR_CFG = json.loads((ROOT / "configs/pair_selection.json").read_text())
RULES = json.loads((ROOT / "configs/statistical_baseline.json").read_text())["rules"]
SETTINGS = json.loads((ROOT / "configs/api.json").read_text())["analysis"]


def synthetic(cointegrated, n=800, seed=7):
    rng = np.random.default_rng(seed)
    x = 4 + np.cumsum(rng.normal(0, 0.015, n))
    if cointegrated:
        noise = np.zeros(n)
        for t in range(1, n):
            noise[t] = 0.5 * noise[t - 1] + rng.normal(0, 0.01)
        y = 0.5 + 0.8 * x + noise
    else:
        y = 4 + np.cumsum(rng.normal(0, 0.015, n))
    dates = pd.bdate_range("2021-01-04", periods=n, name="Date")
    return pd.DataFrame({"AAA_Close": np.exp(y), "BBB_Close": np.exp(x)}, index=dates)


def run(frame, fit_end=None, **kwargs):
    fit_end = frame.index[599] if fit_end is None else fit_end
    return analyse_pair(frame, fit_end, PAIR_CFG, RULES, SETTINGS, **kwargs)


class VerdictTests(unittest.TestCase):
    def test_cointegrated_series_passes(self):
        result = run(synthetic(True))
        self.assertTrue(result["tests"]["cointegrated"])
        self.assertEqual(result["view"], "cointegrated")
        self.assertEqual(result["regression"]["dependent"], "AAA")
        self.assertAlmostEqual(result["regression"]["beta"], 0.8, delta=0.05)
        self.assertEqual(len(result["series"]), 800)
        self.assertEqual(len(result["signals"]), 200)

    def test_independent_walks_fail_with_tests_only(self):
        result = run(synthetic(False))
        self.assertFalse(result["tests"]["cointegrated"])
        self.assertEqual(result["view"], "tests_only")
        self.assertIsNone(result["series"])
        self.assertIsNone(result["signals"])

    def test_exploratory_view_of_failing_pair(self):
        result = run(synthetic(False), exploratory=True)
        self.assertEqual(result["view"], "exploratory")
        self.assertEqual(len(result["signals"]), 200)

    def test_direction_adjustment(self):
        verdict = decide(0.03, 0.2, 1, 0.05)
        self.assertAlmostEqual(verdict["eg_pair_pvalue"], 0.06)
        self.assertFalse(verdict["cointegrated"])
        self.assertTrue(decide(0.02, 0.2, 1, 0.05)["cointegrated"])
        self.assertFalse(decide(0.02, 0.2, 0, 0.05)["cointegrated"])

    def test_later_prices_do_not_change_the_fit(self):
        frame = synthetic(True)
        changed = frame.copy()
        changed.iloc[600:] *= 1.3
        first, second = run(frame), run(changed)
        for key in ("tests", "regression", "normalization", "integration"):
            self.assertEqual(first[key], second[key], key)
        self.assertEqual(first["series"][:600], second["series"][:600])


class WindowTests(unittest.TestCase):
    def test_session_minimums(self):
        dates = pd.bdate_range("2021-01-04", periods=600)
        split_sessions(dates, dates[503], 504, 20)
        with self.assertRaisesRegex(InputError, "503 sessions"):
            split_sessions(dates, dates[502], 504, 20)
        with self.assertRaisesRegex(InputError, "19 sessions"):
            split_sessions(dates, dates[580], 504, 20)

    def test_fit_end_on_a_weekend(self):
        dates = pd.bdate_range("2021-01-04", periods=600)
        saturday = dates[550] + pd.Timedelta(days=(5 - dates[550].weekday()) % 7)
        mask = split_sessions(dates, saturday, 504, 20)
        self.assertEqual(dates[mask][-1], saturday - pd.Timedelta(days=1))

    def test_window_after_leap_day(self):
        dates = pd.bdate_range("2022-06-01", "2024-02-29")
        params = fit_window_normalization(pd.Series(np.arange(len(dates), dtype=float), index=dates),
                                          pd.Timestamp("2024-02-29"))
        self.assertEqual(params["fit_start"], "2023-03-01")
        self.assertEqual(params["fit_end"], "2024-02-29")

    def test_known_normalization(self):
        dates = pd.to_datetime(["2025-03-03", "2025-03-04", "2025-03-05"])
        params = fit_window_normalization(pd.Series([1., 2., 3.], index=dates), pd.Timestamp("2025-03-05"))
        self.assertEqual((params["mean"], params["std"], params["nobs"]), (2.0, 1.0, 3))
        self.assertEqual((4 - params["mean"]) / params["std"], 2.0)
        with self.assertRaisesRegex(InputError, "constant"):
            fit_window_normalization(pd.Series([1., 1., 1.], index=dates), pd.Timestamp("2025-03-05"))


class SignalTests(unittest.TestCase):
    def test_entry_hold_exit_entry(self):
        dates = pd.bdate_range("2026-01-02", periods=5)
        rows = walk_signals(pd.Series([-2.1, -2.5, -0.1, 0.0, 2.1], index=dates), -1.9, 2.0, 0.0)
        self.assertEqual([r["action"] for r in rows],
                         ["enter_long", "hold", "hold", "exit", "enter_short"])
        self.assertEqual([r["position"] for r in rows], [0, 1, 1, 1, 0])
        self.assertEqual(rows[0]["previous_z"], -1.9)

    def test_first_session_compared_with_last_fitting_z(self):
        dates = pd.bdate_range("2026-01-02", periods=1)
        self.assertEqual(walk_signals(pd.Series([-2.1], index=dates), -2.05, 2.0, 0.0)[0]["action"], "hold")


if __name__ == "__main__":
    unittest.main()
