"""Compare the Yahoo, IBKR, and Cboe raw snapshots over the formal periods.

This is a data-quality check only. It reads raw files, compares them field by
field, and writes tables; it fits nothing and changes no data.

IBKR's subscriber agreement forbids redistributing its data, so the tables this
module writes never contain per-day IBKR prices, nor per-day differences from
which one could be recovered. IBKR enters only as summary statistics, counts,
dates, and yes/no flags.
"""

import argparse
from pathlib import Path

import pandas as pd

PERIODS = {"historical": ("2018-01-01", "2025-12-31"), "unseen": ("2026-01-01", "2026-07-31")}
STOCKS = ["MSFT", "GOOGL", "NVDA", "AAPL", "AMZN", "META"]
INDICES = ["GSPC", "VIX"]
PRICE_FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close"}
SPLITS = [("AAPL", "2020-08-31"), ("NVDA", "2021-07-20"), ("AMZN", "2022-06-06"),
          ("GOOGL", "2022-07-18"), ("NVDA", "2024-06-10")]
# Cboe publishes VIX to two decimals; anything beyond rounding noise is a mismatch.
VIX_TOLERANCE = 0.005


def read_yahoo(root: Path, period: str, name: str) -> pd.DataFrame:
    frame = pd.read_csv(root / period / f"{name}.csv", parse_dates=["Date"]).set_index("Date")
    start, end = PERIODS[period]
    # Yahoo's VIX file has empty rows on stock-market holidays.
    return frame.loc[start:end].dropna(subset=["Close"])


def read_ibkr(root: Path, period: str, name: str) -> pd.DataFrame:
    frame = pd.read_csv(root / period / f"{name}.csv", parse_dates=["Date"]).set_index("Date")
    start, end = PERIODS[period]
    return frame.loc[start:end]


def read_cboe(root: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(root / f"{name}.csv")
    frame.index = pd.to_datetime(frame.pop("DATE"), format="%m/%d/%Y")
    frame.index.name = "Date"
    return frame


def compare(yahoo_root: Path, ibkr_root: Path, cboe_root: Path) -> dict[str, pd.DataFrame]:
    dates, prices, volume = [], [], []
    for period in PERIODS:
        for name in STOCKS + INDICES:
            y, i = read_yahoo(yahoo_root, period, name), read_ibkr(ibkr_root, period, name)
            common = y.index.intersection(i.index)
            dates.append({
                "period": period, "instrument": name,
                "yahoo_days": len(y), "ibkr_days": len(i), "common_days": len(common),
                "only_yahoo": ";".join(str(d.date()) for d in y.index.difference(i.index)),
                "only_ibkr": ";".join(str(d.date()) for d in i.index.difference(y.index)),
            })
            for y_field, i_field in PRICE_FIELDS.items():
                pct = (i.loc[common, i_field] / y.loc[common, y_field] - 1) * 100
                worst = pct.abs().idxmax()
                prices.append({
                    "period": period, "instrument": name, "field": y_field,
                    "median_abs_diff_pct": pct.abs().median(),
                    "max_abs_diff_pct": pct.abs().max(),
                    "days_over_0_1pct": int((pct.abs() > 0.1).sum()),
                    "worst_date": str(worst.date()),
                })
            if name in STOCKS:
                ratio = i.loc[common, "volume"] / y.loc[common, "Volume"]
                volume.append({"period": period, "instrument": name,
                               "median_ibkr_to_yahoo": ratio.median(),
                               "min_ibkr_to_yahoo": ratio.min(), "max_ibkr_to_yahoo": ratio.max()})

    splits = []
    for name, day in SPLITS:
        y = read_yahoo(yahoo_root, "historical", name)["Close"]
        i = read_ibkr(ibkr_root, "historical", name)["close"]
        pos = y.index.get_loc(pd.Timestamp(day))
        before = y.index[pos - 1]
        agree = lambda d: abs(i.loc[d] / y.loc[d] - 1) < 0.001
        splits.append({"instrument": name, "split_date": day,
                       "ibkr_matches_yahoo_day_before": bool(agree(before)),
                       "ibkr_matches_yahoo_on_split_day": bool(agree(pd.Timestamp(day))),
                       "yahoo_split_day_change_pct": (y.iloc[pos] / y.loc[before] - 1) * 100})

    cboe = read_cboe(cboe_root, "VIX")
    vix_summary, vix_days, cboe_extra = [], [], []
    for period, (start, end) in PERIODS.items():
        official = cboe.loc[start:end, "CLOSE"]
        y = read_yahoo(yahoo_root, period, "VIX")["Close"]
        i = read_ibkr(ibkr_root, period, "VIX")["close"]
        stock_dates = read_yahoo(yahoo_root, period, "GSPC").index
        for day in official.index.difference(stock_dates):
            cboe_extra.append({"period": period, "date": str(day.date()), "cboe_close": official.loc[day]})
        for label, series in [("yahoo", y), ("ibkr", i)]:
            common = series.index.intersection(official.index)
            diff = (series.loc[common] - official.loc[common]).abs()
            vix_summary.append({"period": period, "source": label, "days_compared": len(common),
                                "days_off": int((diff > VIX_TOLERANCE).sum()),
                                "max_abs_diff": diff.max()})
        common = stock_dates.intersection(official.index)
        off = common[((y.reindex(common) - official.loc[common]).abs() > VIX_TOLERANCE)
                     | ((i.reindex(common) - official.loc[common]).abs() > VIX_TOLERANCE)]
        ibkr_vix = read_ibkr(ibkr_root, period, "VIX")
        for day in off:
            ibkr_close = i.get(day)
            vix_days.append({
                "period": period, "date": str(day.date()), "cboe_close": official.loc[day],
                "yahoo_close": y.get(day),
                "yahoo_off": abs(y.get(day) - official.loc[day]) > VIX_TOLERANCE,
                "ibkr_off": abs(ibkr_close - official.loc[day]) > VIX_TOLERANCE,
                "ibkr_above_cboe": bool(ibkr_close > official.loc[day]),
                "ibkr_close_equals_ibkr_high": abs(ibkr_close - ibkr_vix.loc[day, "high"]) < VIX_TOLERANCE,
            })

    return {
        "dates": pd.DataFrame(dates),
        "price_differences": pd.DataFrame(prices),
        "volume_ratio": pd.DataFrame(volume),
        "splits": pd.DataFrame(splits),
        "vix_vs_cboe_summary": pd.DataFrame(vix_summary),
        "vix_vs_cboe_mismatched_days": pd.DataFrame(vix_days),
        "cboe_vix_dates_without_stock_trading": pd.DataFrame(cboe_extra),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yahoo", type=Path, required=True, help="Yahoo snapshot folder")
    parser.add_argument("--ibkr", type=Path, required=True, help="IBKR snapshot folder")
    parser.add_argument("--cboe", type=Path, required=True, help="Cboe snapshot folder")
    parser.add_argument("--out", type=Path, default=Path("outputs/metrics/source_comparison"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, table in compare(args.yahoo, args.ibkr, args.cboe).items():
        table.to_csv(args.out / f"{name}.csv", index=False, float_format="%.6g", lineterminator="\n")
        print(f"{name}: {len(table)} rows")
    print(f"Tables written to {args.out}")


if __name__ == "__main__":
    main()
