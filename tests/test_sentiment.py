"""Known-input checks for the sentiment study."""

import unittest
from datetime import datetime, date, timezone
import json
from pathlib import Path
import tempfile
import pandas as pd

from market_analytics.sentiment.model import predictions, vader_label, read_settings
from market_analytics.sentiment.evaluation import fiqa_label, normalized_text, phrasebank_overlap, texts_with_several_annotations
from market_analytics.sentiment.headlines import date_only, session_date, strip_publisher, matched_companies, clean_snapshot, validate_news_manifest
from market_analytics.sentiment.news import Collector
from market_analytics.sentiment.study import daily_table, weekly_table


class SentimentModelTests(unittest.TestCase):
    def test_saved_label_order_and_score(self):
        labels = {"0": "positive", "1": "negative", "2": "neutral"}
        result = predictions([[0.2, 0.7, 0.1], [0.7, 0.2, 0.1]], labels)
        self.assertEqual(result[0]["predicted_label"], "negative")
        self.assertAlmostEqual(result[1]["score"], 0.5)
        with self.assertRaises(ValueError):
            predictions([[0.2, 0.7, 0.1]], {"0": "LABEL_0", "1": "negative", "2": "neutral"})

    def test_fixed_threshold_boundaries(self):
        self.assertEqual([fiqa_label(x) for x in [-0.31, -0.3, 0.3, 0.31]],
                         ["negative", "neutral", "neutral", "positive"])
        self.assertEqual([vader_label(x) for x in [-0.05, 0.0499, 0.05]],
                         ["negative", "neutral", "positive"])

    def test_phrasebank_containment_is_not_a_word_match(self):
        sentences = [normalized_text("Example company's profit rose by 5%.")]
        self.assertTrue(phrasebank_overlap("The report said: Example company's profit rose by 5%. It hired staff.", sentences))
        self.assertFalse(phrasebank_overlap("Example company's staff increased by 5%.", sentences))
        short = [normalized_text("Thanks all !"), normalized_text("Not yet , though .")]
        self.assertFalse(phrasebank_overlap("Thanks all! Margins have not yet, though, recovered.", short))
        self.assertTrue(phrasebank_overlap("Thanks, all.", short))

    def test_repeated_text_with_a_second_target_counts_as_multiple(self):
        records = [{"sentence": "Alpha wins contract from Beta", "info": [{"target": "Alpha", "sentiment_score": "0.5"}]},
                   {"sentence": "Alpha wins contract from Beta", "info": [{"target": "Beta", "sentiment_score": "-0.4"}]},
                   {"sentence": "Gamma profit rises", "info": [{"target": "Gamma", "sentiment_score": "0.6"}]},
                   {"sentence": "Gamma profit rises", "info": [{"target": "Gamma", "sentiment_score": "0.6"}]}]
        self.assertEqual(texts_with_several_annotations("fiqa", records), {"alpha wins contract from beta"})

    def test_config_cannot_misreport_fixed_thresholds(self):
        settings = json.loads(Path("configs/sentiment.json").read_text(encoding="utf-8"))
        settings["evaluation"]["fiqa_positive_above"] = 0.4
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "configs/sentiment.json"
            path.parent.mkdir()
            path.write_text(json.dumps(settings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "threshold"):
                read_settings(path)


class HeadlineTests(unittest.TestCase):
    def test_pacific_midnight_across_daylight_saving(self):
        for text in ["2026-01-05T08:00:00+00:00", "2026-07-06T07:00:00+00:00", "2026-03-09T07:00:00+00:00"]:
            self.assertTrue(date_only(datetime.fromisoformat(text)))
        self.assertFalse(date_only(datetime.fromisoformat("2026-03-09T08:00:00+00:00")))

    def test_session_timing(self):
        sessions = [date(2026, 1, day) for day in [6, 7, 9, 12]]
        self.assertEqual(session_date(datetime(2026, 1, 6, 21, 30, tzinfo=timezone.utc), sessions, {}), date(2026, 1, 7))
        self.assertEqual(session_date(datetime(2026, 1, 6, 14, tzinfo=timezone.utc), sessions, {}), date(2026, 1, 6))
        self.assertEqual(session_date(datetime(2026, 1, 10, 15, tzinfo=timezone.utc), sessions, {}), date(2026, 1, 12))
        self.assertEqual(session_date(datetime(2026, 1, 9, 18, 1, tzinfo=timezone.utc), sessions, {"2026-01-09": "13:00"}), date(2026, 1, 12))

    def test_titles_and_company_boundaries(self):
        companies = {"NVDA": {"names": ["Nvidia", "NVDA"]}, "MSFT": {"names": ["Microsoft", "MSFT"]}, "AAPL": {"names": ["Apple", "AAPL"]}}
        self.assertEqual(strip_publisher("Nvidia shares rise - Reuters", "Reuters"), ("Nvidia shares rise", False))
        self.assertEqual(matched_companies("Microsoft beats estimates", companies), ["MSFT"])
        self.assertEqual(matched_companies("Pineapple prices climb", companies), [])
        self.assertEqual(set(matched_companies("Nvidia and Microsoft extend deal", companies)), {"NVDA", "MSFT"})


def rss_items(count, day="2026-01-05", title="Microsoft reports results", source="Reuters", prefix=None):
    published = datetime.fromisoformat(day + "T08:00:00+00:00").strftime("%a, %d %b %Y %H:%M:%S GMT")
    prefix = prefix or day
    return ("<rss><channel>" + "".join(
        f'<item><title>{title.format(i=i)} - {source}</title><guid>{prefix}_{i}</guid><link>https://example.invalid/{i}</link><pubDate>{published}</pubDate><source url="https://example.invalid">{source}</source></item>'
        for i in range(count)) + "</channel></rss>").encode()


class CollectorTests(unittest.TestCase):
    def settings(self):
        settings = json.loads(Path("configs/sentiment.json").read_text(encoding="utf-8"))
        settings["rss"]["minimum_interval_seconds"] = 0
        settings["rss"]["retry_delays_seconds"] = []
        return settings

    def test_limit_splits_a_week_but_flags_a_day(self):
        settings, requests = self.settings(), []
        def stub(url, timeout):
            requests.append(url)
            return 200, rss_items(100 if len(requests) == 1 else 1)
        with tempfile.TemporaryDirectory() as temporary:
            collector = Collector(temporary, settings, fetcher=stub, sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-11")
            self.assertEqual(len(requests), 3)
            self.assertEqual([row["status"] for row in collector.manifest["windows"]], ["split", "success", "success"])
        with tempfile.TemporaryDirectory() as temporary:
            collector = Collector(temporary, settings, fetcher=lambda *_: (200, rss_items(100)), sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-05")
            self.assertEqual(collector.manifest["windows"][0]["status"], "capped")

    def test_items_only_in_a_split_response_are_kept(self):
        settings = self.settings()
        bodies = iter([rss_items(100, "2026-01-05", title="Microsoft update {i}", prefix="wide"),
                       rss_items(1, "2026-01-05", title="Microsoft update {i}", prefix="wide"),
                       rss_items(1, "2026-01-06", title="Microsoft outlook {i}", prefix="narrow")])
        with tempfile.TemporaryDirectory() as temporary:
            collector = Collector(temporary, settings, fetcher=lambda *_: (200, next(bodies)), sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-06")
            frame, excluded, _ = clean_snapshot(Path.cwd(), settings, Path(temporary), [date(2026, 1, 5), date(2026, 1, 6)])
            self.assertEqual(len(frame), 101)
            self.assertEqual(frame.loc[frame.guid == "wide_0", "window_id"].item(), "MSFT_2026-01-05_2026-01-05")
            self.assertEqual(int(frame.split_window.sum()), 99)
            self.assertEqual(excluded.reason.tolist(), ["duplicate_guid"])

    def test_failed_request_is_preserved_and_success_is_not_requeried(self):
        settings = self.settings()
        with tempfile.TemporaryDirectory() as temporary:
            collector = Collector(temporary, settings, fetcher=lambda *_: (503, b"unavailable"), sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-05")
            self.assertEqual(collector.manifest["windows"][0]["status"], "failed")
            self.assertEqual(collector.manifest["attempts"][0]["http_status"], 503)
            collector = Collector(temporary, settings, fetcher=lambda *_: (200, rss_items(1)), sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-05")
            def forbidden(*_):
                raise AssertionError("A completed request was repeated")
            collector = Collector(temporary, settings, fetcher=forbidden, sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-05")
            self.assertEqual(len(collector.manifest["attempts"]), 2)

    def test_local_boundaries_and_publisher_deduplication(self):
        settings = self.settings()
        with tempfile.TemporaryDirectory() as temporary:
            def stub(url, timeout):
                return 200, rss_items(1, "2026-01-05")[:-16] + rss_items(1, "2026-01-06").split(b"<channel>",1)[1]
            collector = Collector(temporary, settings, fetcher=stub, sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-05")
            frame, excluded, _ = clean_snapshot(Path.cwd(), settings, Path(temporary), [date(2026, 1, 5), date(2026, 1, 6)])
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.iloc[0].reported_date, "2026-01-05")
            self.assertEqual(excluded.iloc[0].reason, "outside_requested_window")

    def test_same_title_from_two_publishers_keeps_earliest(self):
        settings = self.settings()
        with tempfile.TemporaryDirectory() as temporary:
            body = rss_items(1, "2026-01-06", source="Second Publisher")[:-16] + rss_items(1, "2026-01-05").split(b"<channel>",1)[1]
            collector = Collector(temporary, settings, fetcher=lambda *_: (200, body), sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-06")
            frame, excluded, _ = clean_snapshot(Path.cwd(), settings, Path(temporary), [date(2026, 1, 5), date(2026, 1, 6)])
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.iloc[0].publisher, "Reuters")
            self.assertEqual(excluded.iloc[0].reason, "duplicate_title")

    def test_empty_feed_has_a_usable_exclusion_schema(self):
        settings = self.settings()
        with tempfile.TemporaryDirectory() as temporary:
            collector = Collector(temporary, settings, fetcher=lambda *_: (200, rss_items(0)), sleeper=lambda _: None)
            collector.collect_window("MSFT", "2026-01-05", "2026-01-05")
            frame, excluded, _ = clean_snapshot(Path.cwd(), settings, Path(temporary), [date(2026, 1, 5)])
            self.assertTrue(frame.empty)
            self.assertTrue(excluded.groupby(["ticker", "reason"]).size().empty)

    def test_snapshot_role_and_settings_are_checked(self):
        settings = self.settings()
        with tempfile.TemporaryDirectory() as temporary:
            collector = Collector(temporary, settings, pilot=False, sleeper=lambda _: None)
            with self.assertRaisesRegex(ValueError, "role"):
                validate_news_manifest(collector.manifest, settings, pilot=True)
            settings["companies"]["META"]["query"] = "a different query"
            with self.assertRaisesRegex(ValueError, "settings"):
                validate_news_manifest(collector.manifest, settings, pilot=False)


class AggregationTests(unittest.TestCase):
    def test_failed_or_capped_friday_affects_next_session(self):
        settings = {"start_date": "2026-01-09", "end_date": "2026-01-13", "companies": {"MSFT": {}}}
        scored = pd.DataFrame(columns=["ticker", "analysis_date", "score", "date_only"])
        for status in ["failed", "capped"]:
            manifest = {"windows": [{"ticker": "MSFT", "start": "2026-01-09", "end": "2026-01-09", "status": status},
                                    {"ticker": "MSFT", "start": "2026-01-10", "end": "2026-01-13", "status": "success"}]}
            daily = daily_table(scored, manifest, settings, [date(2026, 1, day) for day in [9, 12, 13]])
            monday = daily.loc[daily.date == "2026-01-12"].iloc[0]
            tuesday = daily.loc[daily.date == "2026-01-13"].iloc[0]
            self.assertTrue(monday.direct_request_complete)
            if status == "failed":
                self.assertFalse(monday.request_complete)
                self.assertTrue(pd.isna(monday.headline_count))
            else:
                self.assertTrue(monday.capped)
            self.assertTrue(tuesday.request_complete)
            self.assertFalse(tuesday.capped)

    def test_empty_success_is_zero_and_failure_is_missing(self):
        settings = {"start_date": "2026-01-05", "end_date": "2026-01-07", "companies": {"MSFT": {}}}
        manifest = {"windows": [{"ticker": "MSFT", "start": "2026-01-05", "end": "2026-01-06", "status": "success"},
                                {"ticker": "MSFT", "start": "2026-01-07", "end": "2026-01-07", "status": "failed"}]}
        scored = pd.DataFrame([{"ticker": "MSFT", "analysis_date": "2026-01-05", "score": 0.5, "date_only": True}])
        daily = daily_table(scored, manifest, settings, [date(2026, 1, day) for day in [5, 6, 7]])
        self.assertEqual(daily.iloc[0].headline_count, 1)
        self.assertEqual(daily.iloc[1].headline_count, 0)
        self.assertTrue(pd.isna(daily.iloc[1].mean_score))
        self.assertTrue(pd.isna(daily.iloc[2].headline_count))
        self.assertFalse(daily.iloc[2].request_complete)

    def test_weekly_score_weights_headlines_and_marks_partial_weeks(self):
        daily = pd.DataFrame([
            {"ticker": "MSFT", "date": "2026-01-01", "headline_count": 2, "observed_headline_count": 2, "mean_score": 0.2, "request_complete": True, "capped": False},
            {"ticker": "MSFT", "date": "2026-01-02", "headline_count": 1, "observed_headline_count": 1, "mean_score": 1.0, "request_complete": True, "capped": False}])
        weekly = weekly_table(daily, ["MSFT"])
        self.assertAlmostEqual(weekly.iloc[0].mean_score, 1.4 / 3)
        self.assertTrue(weekly.iloc[0].partial_study_week)
        self.assertFalse(weekly.iloc[0].comparison_eligible)


if __name__ == "__main__":
    unittest.main()
