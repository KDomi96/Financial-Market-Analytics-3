"""Phase 2 figures, drawn from the same frames and tables the EDA saves."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, LogLocator

from market_analytics.analysis.eda import drawdown_series, split_input, stock_pairs


COLOURS = {"MSFT": "#1f77b4", "GOOGL": "#ff7f0e", "NVDA": "#2ca02c", "AAPL": "#d62728",
           "AMZN": "#9467bd", "META": "#8c564b", "GSPC": "#222222"}
LABELS = {"GSPC": "S&P 500"}
CORRELATION_SCALE = {"cmap": "RdBu_r", "vmin": -1, "vmax": 1}


def label(symbol: str) -> str:
    return LABELS.get(symbol, symbol)


def pair_grid(title: str) -> tuple[Figure, np.ndarray]:
    fig, axes = plt.subplots(5, 3, figsize=(15, 17), constrained_layout=True)
    fig.suptitle(title, fontsize=14)
    return fig, axes.ravel()


def performance_index(closes: pd.DataFrame) -> Figure:
    fig, ax = plt.subplots(figsize=(12, 6.5), constrained_layout=True)
    indexed = 100 * closes / closes.iloc[0]
    for symbol in closes.columns:
        ax.plot(indexed.index, indexed[symbol], color=COLOURS[symbol], label=label(symbol), lw=1.3)
    # NVDA ends far above the others; a log scale keeps the other six readable.
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.set_ylabel("Close indexed to 100 on 2018-01-02 (log scale)")
    ax.set_title("Price performance, 2018-2025 (split-adjusted Close, dividends excluded)")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend(ncol=4, loc="upper left")
    return fig


def drawdowns(closes: pd.DataFrame, returns: pd.DataFrame) -> Figure:
    fig, axes = plt.subplots(4, 2, figsize=(14, 13), sharex=True, sharey=True, constrained_layout=True)
    fig.suptitle("Drawdown from running peak, 2018-2025 (%)", fontsize=14)
    for ax, symbol in zip(axes.ravel(), returns.columns):
        series = drawdown_series(returns[symbol], closes.index[0])
        ax.fill_between(series.index, series, 0, color=COLOURS[symbol], alpha=0.6, lw=0)
        ax.set_title(f"{label(symbol)}: maximum {series.min():.1f}%")
        ax.set_ylabel("% below peak")
        ax.grid(True, alpha=0.3)
    axes.ravel()[-1].set_visible(False)
    return fig


def pair_log_prices(closes: pd.DataFrame, stocks) -> Figure:
    fig, axes = pair_grid("Rebased log prices, log(Close / Close on 2018-01-02)")
    log_prices = np.log(closes[list(stocks)] / closes[list(stocks)].iloc[0])
    for ax, (a, b) in zip(axes, stock_pairs(stocks)):
        for symbol in (a, b):
            ax.plot(log_prices.index, log_prices[symbol], color=COLOURS[symbol], label=symbol, lw=1)
        ax.set_title(f"{a} and {b}")
        ax.set_ylabel("Natural log units")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
    return fig


def pair_return_scatter(returns: pd.DataFrame, pairs: pd.DataFrame) -> Figure:
    fig, axes = pair_grid("Same-day daily returns for each pair (%)")
    # One axis range for all 15 panels, so spreads are comparable between pairs.
    symbols = list(dict.fromkeys(pairs["stock_a"].tolist() + pairs["stock_b"].tolist()))
    limit = np.ceil(returns[symbols].abs().max().max())
    for ax, row in zip(axes, pairs.itertuples()):
        ax.scatter(returns[row.stock_a], returns[row.stock_b], s=4, alpha=0.35, color="#4c72b0", lw=0)
        ax.axhline(0, color="grey", lw=0.6)
        ax.axvline(0, color="grey", lw=0.6)
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        ax.set_aspect("equal")
        ax.set_xlabel(f"{row.stock_a} return (%)")
        ax.set_ylabel(f"{row.stock_b} return (%)")
        ax.set_title(f"{row.stock_a} and {row.stock_b}: r = {row.return_correlation:.2f}, n = {row.return_n}")
    return fig


def heatmap(ax, values: np.ndarray, rows, columns, title: str):
    image = ax.imshow(values, **CORRELATION_SCALE, aspect="auto")
    ax.set_xticks(range(len(columns)), columns)
    ax.set_yticks(range(len(rows)), rows)
    for (i, j), value in np.ndenumerate(values):
        if np.isfinite(value):
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(value) > 0.6 else "black")
    ax.set_title(title)
    return image


def correlation_heatmap(matrix: pd.DataFrame) -> Figure:
    fig, ax = plt.subplots(figsize=(7.5, 6.5), constrained_layout=True)
    image = heatmap(ax, matrix.to_numpy(), matrix.index, matrix.columns,
                    "Daily-return Pearson correlation, 2018-2025")
    fig.colorbar(image, ax=ax, label="Correlation")
    return fig


def benchmark_scatter(returns: pd.DataFrame, benchmark: pd.DataFrame, stocks) -> Figure:
    fig, axes = plt.subplots(2, 3, figsize=(15, 9.5), sharex=True, sharey=True, constrained_layout=True)
    fig.suptitle("Daily stock returns against S&P 500 returns, 2018-2025, with OLS fit", fontsize=14)
    whole = benchmark[benchmark["period"].eq("2018-2025")].set_index("stock")
    x = returns["GSPC"]
    line = np.linspace(x.min(), x.max(), 2)
    for ax, stock in zip(axes.ravel(), stocks):
        fit = whole.loc[stock]
        ax.scatter(x, returns[stock], s=4, alpha=0.35, color=COLOURS[stock], lw=0)
        ax.plot(line, fit["alpha_pct"] + fit["beta"] * line, color="black", lw=1.2)
        ax.axhline(0, color="grey", lw=0.6)
        ax.axvline(0, color="grey", lw=0.6)
        ax.set_title(f"{stock}: beta {fit['beta']:.2f}, R-squared {fit['r_squared']:.2f}")
        ax.set_xlabel("S&P 500 return (%)")
        ax.set_ylabel(f"{stock} return (%)")
        ax.grid(True, alpha=0.3)
    return fig


def annual_pair_heatmap(annual: pd.DataFrame) -> Figure:
    grid = annual.pivot(index="pair", columns="year", values="correlation")
    grid = grid.loc[annual["pair"].drop_duplicates()]
    fig, ax = plt.subplots(figsize=(10, 9), constrained_layout=True)
    image = heatmap(ax, grid.to_numpy(), grid.index, grid.columns,
                    "Daily-return correlation by calendar year")
    fig.colorbar(image, ax=ax, label="Correlation")
    return fig


def rolling_panels(rolling: pd.DataFrame, pairs: pd.DataFrame, window: int) -> Figure:
    fig, axes = pair_grid(f"Trailing {window}-session daily-return correlation (dashed: 2018-2025 value)")
    lower = min(-0.25, np.floor(rolling["correlation"].min() * 4) / 4)
    for ax, row in zip(axes, pairs.itertuples()):
        series = rolling[rolling["pair"].eq(row.pair)]
        ax.plot(pd.to_datetime(series["date"]), series["correlation"], color="#4c72b0", lw=0.9)
        ax.axhline(row.return_correlation, color="black", ls="--", lw=0.9)
        ax.axhline(0, color="grey", lw=0.6)
        # One range for all panels, extended downwards if any window falls below -0.25.
        ax.set_ylim(lower, 1)
        ax.set_title(f"{row.stock_a} and {row.stock_b}")
        ax.set_ylabel("Correlation")
        ax.grid(True, alpha=0.3)
    return fig


def vix_timeline(vix: pd.Series, boundaries: dict) -> Figure:
    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    ax.plot(vix.index, vix, color="#444444", lw=0.9, label="VIX close (Cboe)")
    low, high = boundaries["boundaries"]
    ax.axhline(low, color="#4c72b0", ls="--", lw=1.2, label=f"Low/medium boundary {low:.2f}")
    ax.axhline(high, color="#c44e52", ls="--", lw=1.2, label=f"Medium/high boundary {high:.2f}")
    ax.legend(loc="upper right")
    ax.set_ylabel("VIX index level")
    ax.set_title("VIX close, 2018-2025, with tercile group boundaries")
    ax.grid(True, alpha=0.3)
    return fig


def save_figures(frame: pd.DataFrame, tables: dict, boundaries: dict, config: dict,
                 directory: Path) -> list[Path]:
    closes, returns, vix = split_input(frame, config)
    figures = {
        "performance_index": performance_index(closes),
        "drawdowns": drawdowns(closes, returns),
        "pair_log_prices": pair_log_prices(closes, config["stocks"]),
        "pair_return_scatter": pair_return_scatter(returns, tables["pair_correlations"]),
        "return_correlation_heatmap": correlation_heatmap(tables["return_correlation_matrix"]),
        "benchmark_scatter": benchmark_scatter(returns, tables["benchmark_sensitivity"], config["stocks"]),
        "pair_annual_correlation_heatmap": annual_pair_heatmap(tables["pair_annual_correlations"]),
        "rolling_correlations": rolling_panels(tables["rolling_correlations"], tables["pair_correlations"],
                                               config["rolling_window"]),
        "vix_timeline": vix_timeline(vix, boundaries),
    }
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fig in figures.items():
        path = directory / f"{name}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)
    return paths
