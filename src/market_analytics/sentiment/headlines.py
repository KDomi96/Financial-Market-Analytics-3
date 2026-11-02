"""Parse saved RSS items and apply the study's fixed headline rules."""

from datetime import datetime, time, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import pandas as pd

from market_analytics.sentiment.model import file_hash, save_json

PACIFIC = ZoneInfo("America/Los_Angeles")
EASTERN = ZoneInfo("America/New_York")


def date_only(published):
    return published.astimezone(PACIFIC).timetz().replace(tzinfo=None) == time(0)


def session_date(published, sessions, early_closes):
    eastern = published.astimezone(EASTERN)
    for day in sessions:
        close = time.fromisoformat(early_closes.get(day.isoformat(), "16:00"))
        if day > eastern.date() or (day == eastern.date() and eastern.timetz().replace(tzinfo=None) <= close):
            return day
    return None


def strip_publisher(title, publisher):
    suffix = " - " + publisher
    if publisher and title.endswith(suffix):
        return title[:-len(suffix)], False
    return title, True


def matched_companies(title, companies):
    return [ticker for ticker, item in companies.items()
            if any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", title, re.IGNORECASE)
                   for name in item["names"])]


def title_key(title):
    return " ".join(unicodedata.normalize("NFKC", title).lower().split())


def parse_feed(body):
    channel = ET.fromstring(body).find("channel")
    if channel is None:
        raise ValueError("Response is not an RSS channel")
    result = []
    for index, item in enumerate(channel.findall("item")):
        publisher = item.find("source")
        row = {"raw_title": item.findtext("title", ""), "google_news_url": item.findtext("link", ""),
               "guid": item.findtext("guid", ""), "reported_time_raw": item.findtext("pubDate", ""),
               "publisher": publisher.text or "" if publisher is not None else "",
               "publisher_source_url": publisher.get("url", "") if publisher is not None else ""}
        try:
            published = parsedate_to_datetime(row["reported_time_raw"])
            if published.tzinfo is None or not row["raw_title"].strip():
                raise ValueError("Missing title or timezone")
            published = published.astimezone(timezone.utc)
            row.update({"reported_time_utc": published.isoformat(), "reported_date": published.date().isoformat(),
                        "date_only": date_only(published), "parse_error": ""})
        except (ValueError, TypeError, OverflowError) as error:
            row.update({"reported_time_utc": "", "reported_date": "", "date_only": False, "parse_error": str(error)})
        row["guid"] = row["guid"] or row["google_news_url"] or hashlib.sha256(
            f"{index}|{row['raw_title']}|{row['reported_time_raw']}".encode()).hexdigest()
        result.append(row)
    return result


def clean_snapshot(root, settings, snapshot, sessions):
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    validate_news_manifest(manifest, settings)
    kept, excluded, seen = [], [], set()
    # Google's results do not add up across windows: a split window's 100-item
    # response holds items its narrower requests never returned. Read it after
    # them, so an item both returned keeps the narrower request's copy.
    for window in sorted(manifest["windows"], key=lambda row: row["status"] == "split"):
        if window["status"] not in {"success", "capped", "split"}:
            continue
        response_path = snapshot / window["response_file"]
        if file_hash(response_path) != window["sha256"]:
            raise ValueError(f"RSS response changed: {response_path.name}")
        for item in parse_feed(response_path.read_bytes()):
            row = {**item, "ticker": window["ticker"], "window_id": window["id"],
                   "collected_at_utc": window["collected_at_utc"], "capped_window": window["status"] == "capped",
                   "split_window": window["status"] == "split"}
            row["headline_id"] = hashlib.sha256(f"{row['ticker']}|{row['guid']}".encode()).hexdigest()[:24]
            reason = None
            if row["parse_error"]:
                reason = "invalid_item"
            elif not window["start"] <= row["reported_date"] <= window["end"]:
                reason = "outside_requested_window"
            elif (row["ticker"], row["guid"]) in seen:
                reason = "duplicate_guid"
            else:
                # An out-of-window copy must not hide the valid copy in a later window.
                seen.add((row["ticker"], row["guid"]))
                row["text"], row["publisher_suffix_unmatched"] = strip_publisher(row["raw_title"], row["publisher"])
                matches = matched_companies(row["text"], settings["companies"])
                if row["ticker"] not in matches:
                    reason = "unrelated_company"
                elif len(matches) > 1:
                    reason = "multiple_companies"
                else:
                    published = datetime.fromisoformat(row["reported_time_utc"])
                    analysis_day = published.astimezone(PACIFIC).date() if row["date_only"] else session_date(
                        published, sessions, settings["early_closes"])
                    row["analysis_date"] = analysis_day.isoformat() if analysis_day else None
                    if not analysis_day or not settings["start_date"] <= row["analysis_date"] <= settings["end_date"]:
                        reason = "no_session_within_study"
            if reason:
                excluded.append({**row, "reason": reason})
            else:
                kept.append(row)
    columns = ["headline_id", "ticker", "text", "raw_title", "publisher", "publisher_source_url", "google_news_url",
               "guid", "reported_time_raw", "reported_time_utc", "reported_date", "date_only", "analysis_date",
               "collected_at_utc", "window_id", "capped_window", "split_window", "publisher_suffix_unmatched",
               "parse_error"]
    frame = pd.DataFrame(kept, columns=columns)
    if not frame.empty:
        frame["normalized_title"] = frame.text.map(title_key)
        frame = frame.sort_values(["reported_time_utc", "collected_at_utc", "headline_id"], kind="stable")
        duplicate = frame.duplicated(["ticker", "normalized_title"], keep="first")
        excluded.extend({**row, "reason": "duplicate_title"} for row in frame.loc[duplicate].to_dict("records"))
        frame = frame.loc[~duplicate].drop(columns="normalized_title").reset_index(drop=True)
    exclusion_frame = pd.DataFrame(excluded, columns=columns + ["reason"])
    return frame, exclusion_frame, manifest


def validate_news_manifest(manifest, settings, pilot=None):
    from market_analytics.sentiment.news import planned_windows

    if pilot is not None and manifest["pilot"] != pilot:
        raise ValueError("News snapshot has the wrong pilot/full role")
    acquisition = {key: settings[key] for key in ["start_date", "end_date", "companies", "rss", "pilot"]}
    fingerprint = hashlib.sha256(json.dumps(acquisition, sort_keys=True).encode()).hexdigest()
    if manifest["settings_sha256"] != fingerprint:
        raise ValueError("Saved news acquisition settings differ")
    if manifest["root_windows"] != planned_windows(settings, manifest["pilot"]):
        raise ValueError("Saved news windows differ from the adopted pilot/full plan")


def pilot_report(root, settings, snapshot, sessions):
    frame, exclusions, manifest = clean_snapshot(root, settings, snapshot, sessions)
    validate_news_manifest(manifest, settings, pilot=True)
    rows = []
    for window in manifest["root_windows"]:
        subset = frame.loc[(frame.ticker == window["ticker"]) & frame.reported_date.between(window["start"], window["end"])]
        leaves = [item for item in manifest["windows"] if item["ticker"] == window["ticker"]
                  and window["start"] <= item["start"] <= item["end"] <= window["end"] and item["status"] != "split"]
        covered = {day.strftime("%Y-%m-%d") for item in leaves if item["status"] in {"success", "capped"}
                   for day in pd.date_range(item["start"], item["end"])}
        expected = set(pd.date_range(window["start"], window["end"]).strftime("%Y-%m-%d"))
        complete = covered == expected and all(item["status"] in {"success", "capped"} for item in leaves)
        capped = any(item["status"] == "capped" for item in leaves)
        rows.append({"ticker": window["ticker"], "start": window["start"], "end": window["end"],
                     "request_complete": complete, "capped": capped, "kept_headlines": len(subset),
                     "publishers": int(subset.publisher.nunique()),
                     "date_only_share": float(subset.date_only.mean()) if len(subset) else None,
                     "usable": complete and not capped and len(subset) >= settings["pilot"]["minimum_headlines_per_week"]})
    coverage = pd.DataFrame(rows)
    counts = coverage.groupby("ticker").usable.sum().astype(int).to_dict()
    supported = [ticker for ticker, count in counts.items() if count >= settings["pilot"]["minimum_usable_weeks"]]
    report = {"snapshot": snapshot.relative_to(root).as_posix(), "usable_weeks": counts,
              "supported_companies": supported, "passed": len(supported) >= settings["pilot"]["minimum_companies"],
              "kept": len(frame), "excluded": len(exclusions),
              "exclusion_counts": exclusions.reason.value_counts().to_dict() if len(exclusions) else {},
              "scored": False}
    directory = root / settings["paths"]["metrics"]
    directory.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(directory / "pilot_coverage.csv", index=False)
    frame.groupby(["ticker", "reported_date"]).size().rename("count").to_csv(directory / "pilot_daily_counts.csv")
    frame.groupby(["ticker", "publisher"]).size().rename("count").to_csv(directory / "pilot_publishers.csv")
    frame.groupby("ticker").publisher_suffix_unmatched.sum().to_csv(directory / "pilot_title_format.csv")
    frame.assign(month=frame.reported_date.str[:7]).groupby(["ticker", "month"]).date_only.agg(["count", "mean"]).to_csv(directory / "pilot_timestamp_precision.csv")
    interim = root / settings["paths"]["interim"]
    interim.mkdir(parents=True, exist_ok=True)
    frame.to_csv(interim / "pilot_cleaned.csv", index=False)
    exclusions.to_csv(interim / "pilot_excluded.csv", index=False)
    save_json(directory / "pilot_report.json", report)
    return report
