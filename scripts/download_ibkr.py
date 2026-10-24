"""Run with: uv run --locked --with ib_async==2.1.0 python scripts/download_ibkr.py (IB Gateway must be running)."""

from market_analytics.data.ibkr import main


if __name__ == "__main__":
    main()
