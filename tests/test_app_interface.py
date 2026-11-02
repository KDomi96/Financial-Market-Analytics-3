"""Drive the Streamlit page against a live API and compare what it shows with the API's responses."""

import json
import os
import socket
import threading
import time
import unittest
from pathlib import Path

import httpx
import uvicorn
from streamlit.testing.v1 import AppTest

from market_analytics.api.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/api.json"
API = json.loads(CONFIG.read_text())
NEEDED = [API["historical"], API["unseen"], API["manifest"], API["pair_ranking"], *API["bundles"].values()]
MISSING = [p for p in NEEDED if not (ROOT / p).exists()]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(MISSING, f"Saved project files not present: {MISSING}")
class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        port = free_port()
        cls.url = f"http://127.0.0.1:{port}"
        cls.server = uvicorn.Server(uvicorn.Config(create_app(CONFIG), port=port, log_level="warning"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(300):
            if cls.server.started:
                break
            time.sleep(0.1)
        cls.previous_url = os.environ.get("API_URL")
        os.environ["API_URL"] = cls.url

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        if cls.previous_url is None:
            os.environ.pop("API_URL", None)
        else:
            os.environ["API_URL"] = cls.previous_url

    def api_analysis(self, pair_id, exploratory=False):
        sample = httpx.get(f"{self.url}/samples/{pair_id}").content
        return httpx.post(f"{self.url}/analyze", files={"file": ("p.csv", sample, "text/csv")},
                          data={"fit_end": "2025-12-31", "exploratory": str(exploratory).lower()},
                          timeout=120).json()

    def page(self, pair_id, exploratory=False):
        at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=120).run()
        at.sidebar.selectbox[0].select(pair_id)
        at.sidebar.checkbox[0].set_value(exploratory)
        at.sidebar.button[0].click()
        return at.run()

    def test_passing_pair_matches_api(self):
        at, expected = self.page("AMZN_META"), self.api_analysis("AMZN_META")
        self.assertFalse(at.exception)
        self.assertIn("AMZN_META is cointegrated", at.success[0].value)
        metrics = {m.label: m.value for m in at.metric}
        self.assertEqual(metrics["Engle-Granger p, direction-adjusted (pass)"],
                         f"{expected['tests']['eg_pair_pvalue']:.4f}")
        for label, key in [("Long entries", "long_entries"), ("Short entries", "short_entries"), ("Exits", "exits")]:
            self.assertEqual(metrics[label], str(expected["signal_counts"][key]))
        self.assertEqual(len(at.get("vega_lite_chart")), 2)
        self.assertTrue(any("Phase 3 rank 1" in i.value for i in at.info))

    def test_failing_pair_shows_tests_only(self):
        at = self.page("NVDA_AMZN")
        self.assertFalse(at.exception)
        self.assertIn("not cointegrated", at.error[0].value)
        self.assertEqual(len(at.get("vega_lite_chart")), 0)

    def test_exploratory_view_is_labelled(self):
        at, expected = self.page("NVDA_AMZN", exploratory=True), self.api_analysis("NVDA_AMZN", True)
        self.assertTrue(any("Exploratory view" in w.value for w in at.warning))
        metrics = {m.label: m.value for m in at.metric}
        self.assertEqual(metrics["Long entries"], str(expected["signal_counts"]["long_entries"]))

    def test_forecast_panel(self):
        at = self.page("AMZN_META")
        [b for b in at.button if b.label == "Forecast five sessions"][0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(any("persistence" in i.value for i in at.info))
        self.assertTrue(any("Origin 2026-03-16" in m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()
