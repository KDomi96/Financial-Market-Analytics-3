"""The API's single-pair analysis must reproduce Phases 3 and 4 on the project's prices."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from market_analytics.api.analysis import analyse_pair
from market_analytics.api.forecast import BundleUnavailable, forecast_pair, load_registry
from market_analytics.api.prices import InputError, parse_prices

ROOT = Path(__file__).resolve().parents[1]
API = json.loads((ROOT / "configs/api.json").read_text())
PAIR_CFG = json.loads((ROOT / "configs/pair_selection.json").read_text())
RULES = json.loads((ROOT / "configs/statistical_baseline.json").read_text())["rules"]
TOL = PAIR_CFG["tolerance"]
NEEDED = [API["historical"], API["unseen"], API["pair_ranking"],
          "artifacts/statistical/phase4_v1/AMZN_META/normalization_2025.json",
          "data/processed/statistical_baseline/unseen_zscores.csv",
          "outputs/backtests/statistical_baseline/phase4_v1/unseen/signals.csv"]
MISSING = [p for p in NEEDED if not (ROOT / p).exists()]
SIGNAL_COLUMNS = ["position", "long_crossing", "short_crossing", "eligible_long", "eligible_short",
                  "exit_signal", "action"]


def project_csv(a, b):
    """The project's closing prices in the upload format, so the parser is part of the check."""
    frames = [pd.read_csv(ROOT / API[k], usecols=["Date", f"{a}_Close", f"{b}_Close"])
              for k in ("historical", "unseen")]
    frame = pd.concat(frames).rename(columns={f"{a}_Close": a, f"{b}_Close": b})
    return frame.to_csv(index=False, float_format="%.17g").encode()


@unittest.skipIf(MISSING, f"Phase 3/4 outputs not present: {MISSING}")
class ReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ranking = pd.read_csv(ROOT / API["pair_ranking"])
        cls.results = {}
        for pair_id, (a, b), exploratory in [("AMZN_META", ("AMZN", "META"), False),
                                              ("NVDA_AMZN", ("NVDA", "AMZN"), True)]:
            prices = parse_prices(project_csv(a, b))
            cls.results[pair_id] = analyse_pair(prices, "2025-12-31", PAIR_CFG, RULES, API["analysis"],
                                                exploratory=exploratory, ranking=ranking)

    def test_verdicts(self):
        amzn_meta = self.results["AMZN_META"]
        self.assertTrue(amzn_meta["tests"]["cointegrated"])
        self.assertAlmostEqual(amzn_meta["tests"]["eg_pair_pvalue"], 0.0284, places=4)
        self.assertAlmostEqual(amzn_meta["tests"]["johansen"]["trace_stat_r0"], 17.60, places=2)
        self.assertAlmostEqual(amzn_meta["tests"]["johansen"]["trace_critical_r0_95"], 15.49, places=2)
        self.assertFalse(self.results["NVDA_AMZN"]["tests"]["cointegrated"])
        self.assertEqual(self.results["NVDA_AMZN"]["view"], "exploratory")
        self.assertEqual(amzn_meta["phase3"]["evidence_label"], "exploratory")

    def test_regression_and_normalization_match_artifacts(self):
        for pair_id, result in self.results.items():
            with self.subTest(pair=pair_id):
                ols_dir = ROOT / "artifacts/statistical/phase3_v1" / pair_id
                ols = json.loads(next(ols_dir.glob("ols_*.json")).read_text())
                norm = json.loads((ROOT / "artifacts/statistical/phase4_v1" / pair_id /
                                   "normalization_2025.json").read_text())
                reg, fitted = result["regression"], result["normalization"]
                self.assertEqual((reg["dependent"], reg["independent"]), (ols["dependent"], ols["independent"]))
                np.testing.assert_allclose([reg["intercept"], reg["beta"]], [ols["intercept"], ols["beta"]], **TOL)
                np.testing.assert_allclose([fitted["mean"], fitted["std"]], [norm["mean"], norm["std"]], **TOL)
                self.assertEqual((fitted["fit_start"], fitted["fit_end"], fitted["nobs"]),
                                 ("2025-01-02", "2025-12-31", 250))

    def test_unseen_zscores_and_signals_match_phase4(self):
        zscores = pd.read_csv(ROOT / "data/processed/statistical_baseline/unseen_zscores.csv")
        signals = pd.read_csv(ROOT / "outputs/backtests/statistical_baseline/phase4_v1/unseen/signals.csv")
        self.assertEqual((len(zscores), len(signals)), (290, 290))
        for pair_id, result in self.results.items():
            with self.subTest(pair=pair_id):
                served = pd.DataFrame(result["signals"])
                saved_z = zscores[zscores.pair_id == pair_id]
                saved = signals[signals.pair_id == pair_id].reset_index(drop=True)
                self.assertEqual(served.date.tolist(), saved_z.Date.tolist())
                np.testing.assert_allclose(served.zscore, saved_z.zscore, **TOL)
                np.testing.assert_allclose(served.previous_z, saved.previous_z, **TOL)
                pd.testing.assert_frame_equal(served[SIGNAL_COLUMNS], saved[SIGNAL_COLUMNS], check_dtype=False)


FORECASTS = "outputs/predictions/lstm/phase5_v2/unseen/forecasts.csv"
BUNDLE_MISSING = [p for p in [FORECASTS, *API["bundles"].values()] if not (ROOT / p).exists()]


@unittest.skipIf(MISSING or BUNDLE_MISSING, f"Phase 5 outputs not present: {MISSING + BUNDLE_MISSING}")
class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(ROOT, API["bundles"], API["startup_tolerance"])
        cls.calendar = pd.DatetimeIndex(pd.concat(
            [pd.read_csv(ROOT / API[k], usecols=["Date"]) for k in ("historical", "unseen")]).Date)
        cls.prices = parse_prices(project_csv("AMZN", "META"))

    def serve(self, prices, registry=None):
        return forecast_pair(prices, registry or self.registry, self.calendar, API["forecast"])

    def test_bundles_pass_startup_check(self):
        self.assertEqual(len(self.calendar), 2156)
        for pair_id, entry in self.registry.items():
            with self.subTest(pair=pair_id):
                self.assertEqual(entry["status"], "ok", entry["error"])
                self.assertLessEqual(entry["max_abs_difference"], 1e-6)

    def test_matches_saved_unseen_forecasts(self):
        saved = pd.read_csv(ROOT / FORECASTS)
        for (a, b), pair_id in [(("AMZN", "META"), "AMZN_META"), (("NVDA", "AMZN"), "NVDA_AMZN")]:
            rows = saved[(saved.pair_id == pair_id) & (saved.origin == "2026-03-16")].sort_values("horizon")
            with self.subTest(pair=pair_id):
                self.assertEqual(len(rows), 5)
                prices = parse_prices(project_csv(a, b))
                result = self.serve(prices.loc[:"2026-03-16"].iloc[-39:])
                served = pd.DataFrame(result["forecasts"])
                np.testing.assert_allclose(served.forecast_z, rows.forecast_z, rtol=0, atol=1e-6)
                self.assertEqual(served.target_date.tolist(), rows.target_date.tolist())
                self.assertAlmostEqual(result["origin_z"], rows.origin_z.iloc[0], places=9)

    def test_last_session_origin_has_no_later_dates(self):
        result = self.serve(self.prices)
        self.assertEqual(result["origin"], "2026-07-31")
        self.assertEqual([f["target_date"] for f in result["forecasts"]], [None] * 5)

    def test_rejections(self):
        with self.assertRaisesRegex(InputError, "38 sessions"):
            self.serve(self.prices.iloc[-38:])
        with self.assertRaisesRegex(InputError, "is missing"):
            self.serve(self.prices.iloc[-60:].drop(self.prices.index[-30]))
        late = self.prices.iloc[-40:].copy()
        late.index = late.index[:-1].append(pd.DatetimeIndex(["2026-08-03"]))
        with self.assertRaisesRegex(InputError, "after 2026-07-31"):
            self.serve(late)
        other = self.prices.iloc[-40:].set_axis(["MSFT_Close", "AAPL_Close"], axis=1)
        with self.assertRaisesRegex(InputError, "No saved model for MSFT_AAPL"):
            self.serve(other)

    def test_changed_weights_disable_only_that_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "AMZN_META"
            shutil.copytree(ROOT / API["bundles"]["AMZN_META"], copy)
            with open(copy / "model.pt", "ab") as handle:
                handle.write(b"\0")
            registry = load_registry(tmp, {"AMZN_META": "AMZN_META"}, API["startup_tolerance"])
        self.assertEqual(registry["AMZN_META"]["status"], "failed")
        self.assertIn("changed weights", registry["AMZN_META"]["error"])
        with self.assertRaises(BundleUnavailable):
            self.serve(self.prices.iloc[-40:], registry)


if __name__ == "__main__":
    unittest.main()
