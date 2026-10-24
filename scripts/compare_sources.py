"""Run with: uv run --locked python scripts/compare_sources.py --yahoo <snapshot> --ibkr <snapshot> --cboe <snapshot>."""

from market_analytics.data.source_comparison import main


if __name__ == "__main__":
    main()
