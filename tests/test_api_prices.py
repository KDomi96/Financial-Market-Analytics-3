"""Uploaded price files that must be rejected, and the ones that must not."""

import unittest

from market_analytics.api.prices import InputError, parse_prices

GOOD = "Date,AMZN,META\n2025-01-02,220.2,599.2\n2025-01-03,224.2,604.6\n"


def body(*rows, header="Date,AMZN,META"):
    return ("\n".join([header, *rows]) + "\n").encode()


class PriceFileTests(unittest.TestCase):
    def rejects(self, content, fragment, **limits):
        with self.assertRaises(InputError) as caught:
            parse_prices(content, **limits)
        self.assertIn(fragment, str(caught.exception))

    def test_valid_file(self):
        frame = parse_prices(GOOD.encode())
        self.assertEqual(list(frame.columns), ["AMZN_Close", "META_Close"])
        self.assertEqual(str(frame.index[1].date()), "2025-01-03")
        self.assertEqual(frame.iloc[1, 1], 604.6)

    def test_byte_order_mark_and_crlf_accepted(self):
        frame = parse_prices(b"\xef\xbb\xbf" + GOOD.replace("\n", "\r\n").encode())
        self.assertEqual(len(frame), 2)

    def test_header_problems(self):
        self.rejects(body("2025-01-02,1", header="Date,AMZN"), "header")
        self.rejects(body("2025-01-02,1,2,3", header="Date,AMZN,META,MSFT"), "header")
        self.rejects(body("2025-01-02,1,2", header="Date,AMZN,AMZN"), "differ")
        self.rejects(body("2025-01-02,1,2", header="Date,amzn,META"), "Ticker")

    def test_dates(self):
        self.rejects(body("2025/01/02,1,2"), "YYYY-MM-DD")
        self.rejects(body("2025-02-30,1,2"), "calendar date")
        self.rejects(body("2025-01-02,1,2", "2025-01-02,1,2"), "Line 3: date 2025-01-02 is repeated")
        self.rejects(body("2025-01-03,1,2", "2025-01-02,1,2"), "earlier")

    def test_prices(self):
        for cell, fragment in [("", "empty"), ("abc", "not a number"), ("nan", "finite"),
                               ("inf", "finite"), ("-inf", "finite"), ("1_000", "not a number"),
                               ("0", "above zero"), ("-5", "above zero")]:
            with self.subTest(cell=cell):
                self.rejects(body("2025-01-02,1,2", f"2025-01-03,{cell},2"), "Line 3")
                self.rejects(body("2025-01-02,1,2", f"2025-01-03,{cell},2"), fragment)

    def test_missing_field(self):
        self.rejects(body("2025-01-02,1"), "Line 2 has 2 fields")

    def test_size_limits(self):
        self.rejects(GOOD.encode() + b"x" * 100, "larger", max_bytes=50)
        dates = [f"20{y:02d}-{m:02d}-{d:02d}" for y in range(30) for m in range(1, 13) for d in range(1, 29)]
        self.rejects(body(*[f"{day},1,2" for day in dates[:10001]]), "more than 10000")
        self.assertEqual(len(parse_prices(body(*[f"{day},1,2" for day in dates[:10000]]))), 10000)

    def test_empty(self):
        self.rejects(b"", "empty")
        self.rejects(b"Date,AMZN,META\n", "no price rows")


if __name__ == "__main__":
    unittest.main()
