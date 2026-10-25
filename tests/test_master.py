"""Small examples for alignment, return units, and period isolation."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from market_analytics.data.master import (
    STOCKS, align_sources, assemble_master, build_master, validate_source,
)


def prices(dates=("2025-12-30", "2025-12-31")):
    return pd.DataFrame(
        {"Open": [10., 11.], "High": [12., 13.], "Low": [9., 10.],
         "Close": [10., 12.], "Adj Close": [9.5, 11.4], "Volume": [100, 120],
         "Dividends": [0., 0.], "Stock Splits": [0., 0.]},
        index=pd.DatetimeIndex(dates, name="Date"),
    )


def aligned(dates=("2025-12-30", "2025-12-31")):
    frame = prices(dates)
    vix = frame[["Open", "High", "Low", "Close"]].copy()
    return align_sources({symbol: frame.copy() for symbol in STOCKS}, frame, vix)[0]


class MasterTests(unittest.TestCase):
    def test_return_units_first_missing_and_reference_fields(self):
        master = assemble_master(aligned())
        self.assertTrue(pd.isna(master.iloc[0]["MSFT_Return"]))
        self.assertAlmostEqual(master.iloc[1]["MSFT_Return"], 20.)
        self.assertEqual(master.iloc[1]["MSFT_AdjClose"], 11.4)
        self.assertEqual(len(master.columns), 48)
        self.assertEqual(master.iloc[0]["Year"], 2025)
        self.assertEqual(master.iloc[0]["Quarter"], 4)
        self.assertNotIn("MSFT_Dividends", master.columns)

    def test_first_unseen_return_uses_prior_close(self):
        history = aligned()
        unseen = aligned(("2026-01-02", "2026-01-05"))
        master = assemble_master(unseen, prior_close=history.iloc[-1])
        self.assertAlmostEqual(master.iloc[0]["MSFT_Return"], -100 / 6)
        with self.assertRaisesRegex(ValueError, "prior close.*earlier"):
            assemble_master(unseen, prior_close=unseen.iloc[0])

    def test_missing_and_extra_stock_dates_fail(self):
        frame = prices()
        stocks = {symbol: frame.copy() for symbol in STOCKS}
        stocks["MSFT"] = frame.iloc[1:]
        with self.assertRaisesRegex(ValueError, "calendar"):
            align_sources(stocks, frame, frame)
        stocks["MSFT"] = frame.rename(index={frame.index[0]: pd.Timestamp("2025-12-29")})
        with self.assertRaisesRegex(ValueError, "calendar"):
            align_sources(stocks, frame, frame)

    def test_duplicate_unsorted_and_missing_values_fail_without_changes(self):
        for frame in (pd.concat([prices(), prices().iloc[-1:]]), prices().iloc[::-1]):
            with self.assertRaises(ValueError):
                validate_source(frame, "MSFT", stock=True)
        for field, value in (("Close", float("nan")), ("High", 9.),
                             ("Volume", 1.5), ("Open", float("inf"))):
            frame = prices()
            frame[field] = frame[field].astype(float)
            frame.loc[frame.index[0], field] = value
            before = frame.copy(deep=True)
            with self.assertRaises(ValueError):
                validate_source(frame, "MSFT", stock=True)
            pd.testing.assert_frame_equal(frame, before)

    def test_missing_vix_fails_and_extra_vix_is_logged(self):
        frame = prices()
        stocks = {symbol: frame.copy() for symbol in STOCKS}
        with self.assertRaisesRegex(ValueError, "VIX.*missing"):
            align_sources(stocks, frame, frame.iloc[1:])
        vix = pd.concat([frame, frame.iloc[-1:].rename(
            index={frame.index[-1]: pd.Timestamp("2026-01-01")})])
        result, excluded = align_sources(stocks, frame, vix)
        self.assertEqual(len(result), 2)
        self.assertEqual(excluded["Date"].tolist(), ["2026-01-01"])
        self.assertEqual(result["VIX_Close"].tolist(), [10., 12.])

    def test_invalid_benchmark_actions_cannot_enter_checkpoint(self):
        frame = prices()
        frame.loc[frame.index[0], "Dividends"] = float("nan")
        with self.assertRaisesRegex(ValueError, "dividend or split"):
            validate_source(frame, "GSPC", benchmark=True)

    def test_historical_build_never_opens_unseen_files_and_checks_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "configs").mkdir()
            yahoo = root / "data/raw/yahoo"
            cboe = root / "data/raw/cboe"
            (yahoo / "historical").mkdir(parents=True)
            cboe.mkdir(parents=True)
            records = []
            for symbol in (*STOCKS, "GSPC"):
                path = yahoo / "historical" / f"{symbol}.csv"
                prices().to_csv(path, lineterminator="\n")
                records.append({"period": "historical", "symbol": "^GSPC" if symbol == "GSPC" else symbol,
                                "file": f"historical/{symbol}.csv", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            records.append({"period": "unseen", "symbol": "MSFT", "file": "unseen/MSFT.csv", "sha256": "not-read"})
            (yahoo / "manifest.json").write_text(json.dumps({"status": "complete", "records": records}))
            vix_path = cboe / "VIX.csv"
            vix = prices().reset_index().rename(columns={"Date": "DATE", "Open": "OPEN", "High": "HIGH", "Low": "LOW", "Close": "CLOSE"})
            vix["DATE"] = vix["DATE"].dt.strftime("%m/%d/%Y")
            vix.to_csv(vix_path, index=False)
            (cboe / "manifest.json").write_text(json.dumps({"status": "complete", "records": [{"name": "VIX", "file": "VIX.csv", "sha256": hashlib.sha256(vix_path.read_bytes()).hexdigest()}]}))
            config = {"sources": {"yahoo": "data/raw/yahoo", "cboe": "data/raw/cboe"},
                      "stocks": list(STOCKS), "periods": {"historical": {"start": "2025-12-30", "end": "2025-12-31", "first_session": "2025-12-30", "last_session": "2025-12-31", "rows": 2}},
                      "outputs": {"interim": "data/interim", "processed": "data/processed", "metrics": "outputs/metrics"},
                      "large_move_threshold_percent": 99, "return_checks": []}
            config_path = root / "configs/master_data.json"
            config_path.write_text(json.dumps(config))
            first = build_master(config_path, historical_only=True)
            # An unrelated unseen file must not change the historical result.
            (yahoo / "unseen").mkdir()
            (yahoo / "unseen/MSFT.csv").write_text("invalid unseen data")
            second = build_master(config_path, historical_only=True)
            self.assertEqual(first["outputs"], second["outputs"])
            self.assertIn("market_analytics/data/master.py",
                          [entry["file"] for entry in first["build_files"]])
            path = root / "data/processed/master_historical.csv"
            self.assertNotIn(b"\r\n", path.read_bytes())
            with (yahoo / "historical/MSFT.csv").open("a") as handle:
                handle.write("changed")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                build_master(config_path, historical_only=True)


if __name__ == "__main__":
    unittest.main()
