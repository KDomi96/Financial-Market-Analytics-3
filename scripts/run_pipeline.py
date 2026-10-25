"""Run the batch phases in order: master build, then EDA.

Run with: uv run --locked python scripts/run_pipeline.py [--historical-only]
"""

import argparse
from pathlib import Path

import matplotlib

from market_analytics.analysis.eda import run_eda
from market_analytics.data.master import build_master


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


if __name__ == "__main__":
    main()
