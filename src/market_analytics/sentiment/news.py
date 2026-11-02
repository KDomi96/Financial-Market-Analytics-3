"""Collect Google News RSS with saved responses and resumable date windows."""

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

from market_analytics.sentiment.headlines import parse_feed, pilot_report
from market_analytics.sentiment.model import file_hash, read_settings, save_json


def planned_windows(settings, pilot):
    start, end = date.fromisoformat(settings["start_date"]), date.fromisoformat(settings["end_date"])
    windows = []
    if pilot:
        month = start.replace(day=1)
        while month <= end:
            monday = month + timedelta(days=(-month.weekday()) % 7)
            windows.append((monday, monday + timedelta(days=4)))
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        while start <= end:
            stop = min(start + timedelta(days=(4 - start.weekday()) % 7), end)
            windows.append((start, stop))
            start = stop + timedelta(days=1)
    return [{"ticker": ticker, "start": a.isoformat(), "end": b.isoformat()}
            for ticker in settings["companies"] for a, b in windows]


def fetch(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "market-analytics-research"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class Collector:
    def __init__(self, directory, settings, pilot=False, fetcher=fetch, sleeper=time.sleep):
        self.directory, self.settings = Path(directory), settings
        self.fetcher, self.sleeper, self.last_request = fetcher, sleeper, None
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "manifest.json"
        fingerprint = hashlib.sha256(json.dumps({key: settings[key] for key in
            ["start_date", "end_date", "companies", "rss", "pilot"]}, sort_keys=True).encode()).hexdigest()
        if self.path.exists():
            self.manifest = json.loads(self.path.read_text(encoding="utf-8"))
            if self.manifest["settings_sha256"] != fingerprint or self.manifest["pilot"] != pilot:
                raise ValueError("Resume settings differ from the saved collection")
        else:
            self.manifest = {"status": "interrupted", "pilot": pilot, "settings_sha256": fingerprint,
                             "settings": settings, "code_sha256": file_hash(Path(__file__)),
                             "started_at_utc": datetime.now(timezone.utc).isoformat(),
                             "root_windows": planned_windows(settings, pilot), "windows": [], "attempts": []}
            self.save()

    def save(self):
        save_json(self.path, self.manifest)

    def collect_window(self, ticker, start, end):
        identifier = f"{ticker}_{start}_{end}"
        window = next((row for row in self.manifest["windows"] if row["id"] == identifier), None)
        if window is None:
            window = {"id": identifier, "ticker": ticker, "start": start, "end": end, "status": "pending"}
            self.manifest["windows"].append(window)
            self.save()
        if window["status"] in {"success", "capped"}:
            response_path = self.directory / window["response_file"]
            if file_hash(response_path) != window["sha256"]:
                raise ValueError("Saved RSS response hash differs")
            return
        if window["status"] == "split":
            self.split(window)
            return
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        query = self.settings["companies"][ticker]["query"] + f" after:{a - timedelta(days=1)} before:{b + timedelta(days=1)}"
        rss = self.settings["rss"]
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": query, "hl": rss["language"], "gl": rss["country"], "ceid": rss["edition"]})
        attempts_before = sum(row["window_id"] == identifier for row in self.manifest["attempts"])
        for attempt in range(len(rss["retry_delays_seconds"]) + 1):
            if self.last_request is not None:
                self.sleeper(max(0, rss["minimum_interval_seconds"] - (time.monotonic() - self.last_request)))
            record = {"window_id": identifier, "url": url, "query": query, "attempt": attempts_before + attempt + 1,
                      "collected_at_utc": datetime.now(timezone.utc).isoformat(), "http_status": None}
            retry = False
            try:
                self.last_request = time.monotonic()
                status, body = self.fetcher(url, rss["timeout_seconds"])
                path = self.directory / f"{identifier}_{record['attempt']:02d}.xml"
                path.write_bytes(body)
                record.update({"http_status": status, "response_file": path.name,
                               "bytes": len(body), "sha256": file_hash(path)})
                if status != 200:
                    retry = status == 429 or 500 <= status < 600
                    raise ValueError(f"HTTP {status}")
                items = parse_feed(body)
                window.update({key: record[key] for key in ["response_file", "sha256", "collected_at_utc"]})
                window["items_returned"] = len(items)
                at_limit = len(items) >= rss["result_limit"]
                window["status"] = "split" if at_limit and a < b else "capped" if at_limit else "success"
                record["outcome"] = window["status"]
            except (TimeoutError, urllib.error.URLError, OSError) as error:
                record.update({"outcome": "failed", "error": f"{type(error).__name__}: {error}"})
                retry = True
            except (ValueError, ET.ParseError) as error:
                record.update({"outcome": "failed", "error": f"{type(error).__name__}: {error}"})
            self.manifest["attempts"].append(record)
            if record["outcome"] == "failed":
                window["status"] = "failed"
            self.save()
            if window["status"] == "split":
                self.split(window)
                return
            if window["status"] in {"success", "capped"}:
                print(f"{identifier}: {window['items_returned']} items, {window['status']}", flush=True)
                return
            if not retry or attempt == len(rss["retry_delays_seconds"]):
                print(f"{identifier}: failed ({record['error']})", flush=True)
                return
            self.sleeper(rss["retry_delays_seconds"][attempt])

    def split(self, window):
        start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        middle = start + (end - start) // 2
        self.collect_window(window["ticker"], start.isoformat(), middle.isoformat())
        self.collect_window(window["ticker"], (middle + timedelta(days=1)).isoformat(), end.isoformat())

    def run(self):
        for window in self.manifest["root_windows"]:
            self.collect_window(window["ticker"], window["start"], window["end"])
        self.manifest["status"] = "partial" if any(row["status"] in {"failed", "pending"}
                                                  for row in self.manifest["windows"]) else "complete"
        self.manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/sentiment.json"))
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    root, settings = read_settings(args.config)
    directory = args.resume.resolve() if args.resume else root / settings["paths"]["raw_news"] / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    collector = Collector(directory, settings, args.pilot)
    collector.run()
    print(f"Snapshot: {directory.relative_to(root).as_posix()}", flush=True)
    if args.pilot:
        sessions = pd.to_datetime(pd.read_csv(root / settings["paths"]["zscores"], usecols=["Date"]).Date).dt.date.sort_values().unique().tolist()
        print(json.dumps(pilot_report(root, settings, directory, sessions), indent=2), flush=True)
