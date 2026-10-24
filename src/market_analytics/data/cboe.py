"""Download Cboe's official daily index history files.

Cboe publishes each index's full daily history (1990 onwards for VIX) as one
CSV. The response body is saved byte for byte; period filtering happens later.
"""

import argparse
import hashlib
import io
import json
import platform
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def download_snapshot(config_path: Path) -> Path:
    """Save each configured history file unchanged, plus a manifest."""
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    started = datetime.now(timezone.utc)
    run_dir = project_root / "data/raw/cboe" / started.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "provider": "Cboe Global Markets (official index history files)",
        "started_at_utc": started.isoformat(),
        "versions": {"python": platform.python_version(), "pandas": pd.__version__},
        "representation": "HTTP response bodies saved unchanged",
        "records": [],
        "status": "interrupted",
    }
    try:
        for name, url in config["instruments"].items():
            # urllib follows Cboe's redirect from cdn.cboe.com to cdn-api.cboe.com.
            with urllib.request.urlopen(url, timeout=60) as response:
                body = response.read()
                final_url = response.geturl()
            path = run_dir / f"{name}.csv"
            path.write_bytes(body)
            frame = pd.read_csv(io.BytesIO(body))
            dates = pd.to_datetime(frame["DATE"], format="%m/%d/%Y")
            record = {
                "name": name,
                "url": url,
                "final_url": final_url,
                "file": path.name,
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(body).hexdigest(),
                "rows": len(frame),
                "columns": list(frame.columns),
                "first_date": str(dates.min().date()),
                "last_date": str(dates.max().date()),
                "duplicate_dates": int(dates.duplicated().sum()),
                "missing_close": int(frame["CLOSE"].isna().sum()),
                "rows_in_formal_periods": {
                    period: int(dates.between(p["formal_start"], p["formal_end"]).sum())
                    for period, p in config["periods"].items()
                },
            }
            manifest["records"].append(record)
            print(f"{name}: {record['rows']} rows {record['first_date']} to {record['last_date']}, "
                  f"in periods {record['rows_in_formal_periods']}", flush=True)
        ok = all(r["duplicate_dates"] == 0 and r["missing_close"] == 0 for r in manifest["records"])
        manifest["status"] = "complete" if ok else "failed"
    finally:
        manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    print(f"Snapshot: {run_dir.relative_to(project_root)} ({manifest['status']})", flush=True)
    if manifest["status"] != "complete":
        raise RuntimeError("Cboe download failed validation; inspect manifest.json")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/cboe.json"))
    args = parser.parse_args()
    download_snapshot(args.config)


if __name__ == "__main__":
    main()
