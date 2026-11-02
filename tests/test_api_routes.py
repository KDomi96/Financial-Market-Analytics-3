"""Every route and status code through FastAPI's test client, on the project's saved files."""

import json
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from market_analytics.api.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/api.json"
API = json.loads(CONFIG.read_text())
NEEDED = [API["historical"], API["unseen"], API["manifest"], API["pair_ranking"], *API["bundles"].values()]
MISSING = [p for p in NEEDED if not (ROOT / p).exists()]


def upload(text, name="prices.csv"):
    return {"file": (name, text.encode() if isinstance(text, str) else text, "text/csv")}


@unittest.skipIf(MISSING, f"Saved project files not present: {MISSING}")
class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(create_app(CONFIG))
        cls.client = cls.context.__enter__()
        cls.samples = {p: cls.client.get(f"/samples/{p}").text for p in ("AMZN_META", "NVDA_AMZN", "MSFT_AAPL")}

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_health(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual({b["pair_id"]: b["status"] for b in body["bundles"]},
                         {"AMZN_META": "ok", "NVDA_AMZN": "ok"})

    def test_pairs(self):
        body = self.client.get("/pairs").json()
        self.assertEqual(len(body["pairs"]), 15)
        self.assertEqual(body["last_session"], "2026-07-31")
        with_models = [p["pair_id"] for p in body["pairs"] if p["has_forecast_model"]]
        self.assertEqual(sorted(with_models), ["AMZN_META", "NVDA_AMZN"])
        self.assertEqual({p["evidence_label"] for p in body["pairs"]}, {"exploratory"})

    def test_samples(self):
        lines = self.samples["AMZN_META"].splitlines()
        self.assertEqual(lines[0], "Date,AMZN,META")
        self.assertEqual(len(lines), 2157)
        self.assertEqual(self.client.get("/samples/AMZN_FOO").status_code, 404)
        self.assertEqual(self.client.get("/samples/META_AMZN").status_code, 404)

    def test_analyze_passing_pair(self):
        response = self.client.post("/analyze", files=upload(self.samples["AMZN_META"]),
                                    data={"fit_end": "2025-12-31"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["view"], "cointegrated")
        self.assertEqual(len(body["signals"]), 145)
        self.assertEqual(body["normalization"]["nobs"], 250)
        self.assertIn("overstates", body["phase3"]["note"])

    def test_analyze_failing_pair_and_exploratory_view(self):
        plain = self.client.post("/analyze", files=upload(self.samples["NVDA_AMZN"])).json()
        self.assertEqual(plain["view"], "tests_only")
        self.assertIsNone(plain["series"])
        explored = self.client.post("/analyze", files=upload(self.samples["NVDA_AMZN"]),
                                    data={"exploratory": "true"}).json()
        self.assertEqual(explored["view"], "exploratory")
        self.assertEqual(len(explored["series"]), 2156)

    def test_analyze_rejections(self):
        cases = [(upload("Date,AMZN\n2025-01-02,1\n"), {}, "header"),
                 (upload(self.samples["AMZN_META"]), {"fit_end": "31/12/2025"}, "fit_end"),
                 (upload(self.samples["AMZN_META"]), {"fit_end": "2018-06-30"}, "at least 504"),
                 (upload(self.samples["AMZN_META"]), {"fit_end": "2026-07-20"}, "at least 20"),
                 (upload(b"x" * (API["upload"]["max_bytes"] + 1)), {}, "larger")]
        for files, data, fragment in cases:
            with self.subTest(fragment=fragment):
                response = self.client.post("/analyze", files=files, data=data)
                self.assertEqual(response.status_code, 422)
                self.assertIn(fragment, response.json()["detail"])
        self.assertEqual(self.client.post("/analyze").status_code, 422)

    def test_forecast(self):
        tail = "\n".join(self.samples["AMZN_META"].splitlines()[:1] +
                         self.samples["AMZN_META"].splitlines()[-40:]) + "\n"
        response = self.client.post("/forecast", files=upload(tail), data={"pair": "AMZN_META"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["origin"], "2026-07-31")
        self.assertEqual(len(response.json()["forecasts"]), 5)
        earlier = self.client.post("/forecast", files=upload(self.samples["NVDA_AMZN"]),
                                   data={"origin": "2026-03-16"}).json()
        self.assertEqual(earlier["origin"], "2026-03-16")
        self.assertEqual(earlier["forecasts"][4]["target_date"], "2026-03-23")

    def test_forecast_rejections(self):
        short = "\n".join(self.samples["AMZN_META"].splitlines()[:1] +
                          self.samples["AMZN_META"].splitlines()[-38:]) + "\n"
        cases = [(self.samples["AMZN_META"], {"pair": "NVDA_AMZN"}, "not NVDA_AMZN"),
                 (self.samples["MSFT_AAPL"], {}, "No saved model"),
                 (short, {}, "at least 39"),
                 (self.samples["AMZN_META"], {"origin": "2026-03-15"}, "not a date in the file")]
        for text, data, fragment in cases:
            with self.subTest(fragment=fragment):
                response = self.client.post("/forecast", files=upload(text), data=data)
                self.assertEqual(response.status_code, 422)
                self.assertIn(fragment, response.json()["detail"])


@unittest.skipIf(MISSING, f"Saved project files not present: {MISSING}")
class FailedBundleTests(unittest.TestCase):
    def test_missing_bundle_degrades_only_forecasts(self):
        bundles = {**API["bundles"], "AMZN_META": "artifacts/lstm/missing_bundle"}
        with TestClient(create_app(CONFIG, bundles=bundles)) as client:
            health = client.get("/health").json()
            self.assertEqual(health["status"], "degraded")
            failed = {b["pair_id"]: b for b in health["bundles"]}["AMZN_META"]
            self.assertEqual(failed["status"], "failed")
            self.assertIn("FileNotFoundError", failed["error"])
            sample = client.get("/samples/AMZN_META").text
            self.assertEqual(client.post("/forecast", files=upload(sample)).status_code, 503)
            self.assertEqual(client.post("/analyze", files=upload(sample)).status_code, 200)

    def test_missing_master_stops_startup(self):
        with self.assertRaises(FileNotFoundError):
            with TestClient(create_app(CONFIG, unseen="data/processed/missing.csv")):
                pass


if __name__ == "__main__":
    unittest.main()
