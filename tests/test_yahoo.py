"""Checks for acquisition errors that could silently corrupt later analysis."""

import unittest

import pandas as pd

from market_analytics.data.yahoo import inspect_prices


PERIOD = {
    "start": "2026-01-01", "end_exclusive": "2026-01-07",
    "first_session": "2026-01-02", "last_session": "2026-01-06",
}


def prices():
    return pd.DataFrame(
        {"Open": [10., 10.], "High": [12., 12.], "Low": [9., 9.],
         "Close": [11., 11.], "Adj Close": [11., 11.], "Volume": [100, 100]},
        index=pd.to_datetime(["2026-01-02", "2026-01-06"]),
    )


class AcquisitionValidationTests(unittest.TestCase):
    def test_valid_records(self):
        self.assertEqual(inspect_prices(prices(), PERIOD)["errors"], [])

    def test_unseen_row_cannot_enter_historical_period(self):
        frame = prices()
        frame.loc[pd.Timestamp("2026-01-07")] = frame.iloc[-1]
        self.assertIn("Observations outside the requested period",
                      inspect_prices(frame, PERIOD)["errors"])

    def test_duplicate_dates(self):
        frame = pd.concat([prices(), prices().iloc[-1:]])
        self.assertIn("Duplicate trading dates", inspect_prices(frame, PERIOD)["errors"])

    def test_missing_price_on_a_trading_day_fails(self):
        frame = prices()
        frame.loc[frame.index[0], "Close"] = float("nan")
        self.assertIn("Missing OHLCV or adjusted-close values",
                      inspect_prices(frame, PERIOD)["errors"])

    def test_vix_empty_nontrading_row_is_reported_and_preserved(self):
        frame = prices()
        frame.loc[pd.Timestamp("2026-01-05")] = [float("nan")] * 5 + [0]
        frame = frame.sort_index()
        before = frame.copy(deep=True)
        result = inspect_prices(frame, PERIOD, reference_dates=set(prices().index.date))
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["empty_nontrading_dates"], ["2026-01-05"])
        pd.testing.assert_frame_equal(frame, before)

    def test_vix_empty_trading_row_still_fails(self):
        frame = prices()
        frame.iloc[0] = [float("nan")] * 5 + [0]
        result = inspect_prices(frame, PERIOD, reference_dates=set(prices().index.date))
        self.assertIn("Missing OHLCV or adjusted-close values", result["errors"])


if __name__ == "__main__":
    unittest.main()
