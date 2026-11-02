"""Run the master build, EDA, pair selection, and statistical baseline in order.

Run with: uv run --locked python scripts/run_pipeline.py [--historical-only]
"""

import argparse
from pathlib import Path

import matplotlib

from market_analytics.analysis.eda import run_eda
from market_analytics.cointegration.selection import run_pair_selection
from market_analytics.data.master import build_master
from market_analytics.trading.baseline import run_statistical_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-only", action="store_true",
                        help="Build only the historical master; no Yahoo unseen file is opened")
    args = parser.parse_args()
    matplotlib.use("Agg")
    manifest = build_master(Path("configs/master_data.json"), historical_only=args.historical_only)
    print("Master build: " + ", ".join(f"{period} {data['rows']} rows"
                                       for period, data in manifest["datasets"].items()))
    metadata = run_eda(Path("configs/eda.json"))
    print(f"EDA: {len(metadata['validation'])} checks passed, {len(metadata['outputs'])} tables, "
          f"{len(metadata['figures'])} figures")
    metadata = run_pair_selection(Path("configs/pair_selection.json"))
    print(f"Pair selection: {len(metadata['validation'])} checks passed, "
          f"{len(metadata['outputs'])} tables/data/artifacts, {len(metadata['figures'])} figures")
    for period, result in run_statistical_baseline(Path("configs/statistical_baseline.json"),
                                                  historical_only=args.historical_only).items():
        print(f"Statistical baseline {period}: {result['status']}, {len(result['validation'])} checks")
        if result["status"] != "complete":
            raise RuntimeError("Incomplete baseline accounts")


if __name__ == "__main__":
    main()
