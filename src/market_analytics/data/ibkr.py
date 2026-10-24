"""Download daily IBKR bars for comparison with the Yahoo snapshot.

Needs IB Gateway or TWS running and logged in, with the API enabled and set
to read-only. The connection is opened read-only as well, and nothing about
the account is written to disk.
"""

import argparse
import hashlib
import json
import logging
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd

# ib_async is deliberately not a project dependency: it pins tzdata<2026,
# which would hold back the main environment. Supply it per run instead.
try:
    from ib_async import IB, Index, Stock, util
except ImportError as exc:
    raise SystemExit("ib_async is missing; run with: "
                     "uv run --locked --with ib_async==2.1.0 python scripts/download_ibkr.py") from exc

# IBKR status notices about data-farm connections, not request errors.
FARM_NOTICES = {2104, 2106, 2107, 2119, 2158}


def make_contract(spec: dict):
    if spec["sec_type"] == "STK":
        return Stock(spec["symbol"], spec["exchange"], spec["currency"],
                     primaryExchange=spec.get("primary_exchange", ""))
    if spec["sec_type"] == "IND":
        return Index(spec["symbol"], spec["exchange"], spec["currency"])
    raise ValueError(f"Unsupported security type: {spec['sec_type']}")


def download_snapshot(config_path: Path) -> Path:
    """Save daily TRADES bars exactly as IBKR returns them, plus a manifest.

    IBKR takes an end time and a duration, not a start date. Requesting exactly
    "8 Y" or "7 M" drops the first session of each period, so the configured
    windows are a little wider than the periods. Rows outside the formal period
    are kept and counted in the manifest; later processing filters by date.
    End times are written in UTC because IBKR rejected the US/Eastern form for
    the index contracts.
    """
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    started = datetime.now(timezone.utc)
    run_dir = project_root / "data/raw/ibkr" / started.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)

    logging.getLogger("ib_async").setLevel(logging.CRITICAL)
    ib = IB()
    errors: list[tuple[int, str]] = []
    ib.errorEvent += lambda req_id, code, msg, contract: errors.append((code, msg))
    conn = config["connection"]
    ib.connect(conn["host"], conn["port"], clientId=conn["client_id"], readonly=True, timeout=15)

    manifest = {
        "provider": "Interactive Brokers (IB Gateway, read-only API session)",
        "access_library": "ib_async",
        "started_at_utc": started.isoformat(),
        "versions": {
            "python": platform.python_version(),
            "ib_async": version("ib_async"),
            "pandas": pd.__version__,
            "api_server_version": ib.client.serverVersion(),
        },
        "request_settings": {
            "bar_size": "1 day",
            "what_to_show": "TRADES",
            "use_regular_trading_hours": True,
            "periods": config["periods"],
        },
        "adjustment_policy": "TRADES bars: adjusted for splits, not dividends (IBKR documentation).",
        "records": [],
        "status": "interrupted",
    }
    try:
        for period, req in config["periods"].items():
            (run_dir / period).mkdir()
            for name, spec in config["instruments"].items():
                errors.clear()
                contract = make_contract(spec)
                ib.qualifyContracts(contract)
                bars = ib.reqHistoricalData(
                    contract,
                    endDateTime=req["end_utc"],
                    durationStr=req["duration"],
                    barSizeSetting="1 day",
                    whatToShow="TRADES",
                    useRTH=True,
                    formatDate=1,
                    timeout=120,
                )
                record = {
                    "period": period,
                    "name": name,
                    "contract": {
                        "symbol": contract.symbol,
                        "sec_type": contract.secType,
                        "exchange": contract.exchange,
                        "primary_exchange": contract.primaryExchange,
                        "currency": contract.currency,
                        "con_id": contract.conId,
                    },
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "errors": [e for e in errors if e[0] not in FARM_NOTICES],
                }
                if bars:
                    frame = util.df(bars).rename(columns={"date": "Date"})
                    path = run_dir / period / f"{name}.csv"
                    frame.to_csv(path, index=False, lineterminator="\n")
                    dates = pd.to_datetime(frame["Date"])
                    inside = dates.between(req["formal_start"], req["formal_end"])
                    record.update(
                        file=f"{period}/{name}.csv",
                        rows=len(frame),
                        rows_in_formal_period=int(inside.sum()),
                        first_date_in_formal_period=str(dates[inside].min().date()),
                        last_date_in_formal_period=str(dates[inside].max().date()),
                        first_date=str(frame["Date"].iloc[0]),
                        last_date=str(frame["Date"].iloc[-1]),
                        columns=list(frame.columns),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                else:
                    record.update(file=None, rows=0)
                manifest["records"].append(record)
                print(f"{period:10s} {name:6s} rows={record['rows']:5d} "
                      f"in_period={record.get('rows_in_formal_period', 0):5d} "
                      f"errors={record['errors']}", flush=True)
        ok = all(r["rows"] > 0 and not r["errors"] for r in manifest["records"])
        manifest["status"] = "complete" if ok else "failed"
    finally:
        ib.disconnect()
        manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    print(f"Snapshot: {run_dir.relative_to(project_root)} ({manifest['status']})", flush=True)
    if manifest["status"] != "complete":
        raise RuntimeError("IBKR download incomplete; inspect manifest.json")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/ibkr.json"))
    args = parser.parse_args()
    download_snapshot(args.config)


if __name__ == "__main__":
    main()
