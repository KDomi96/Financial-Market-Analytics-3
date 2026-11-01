"""Figures for the saved historical pair-selection results."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def save_figures(prices, tables, spreads, cfg, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    rows = tables["pair_ranking"].sort_values("pair_order")
    paths = []

    def panels(title):
        fig, axes = plt.subplots(5, 3, figsize=(16, 17), layout="constrained")
        fig.suptitle(title, fontsize=15)
        return fig, axes.ravel()

    def save(fig, name):
        path = directory / name
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)

    fig, axes = panels("Historical log prices and fitted relationships | 2018-2025 | in sample")
    for ax, row in zip(axes, rows.itertuples(), strict=True):
        y = np.log(prices[f"{row.dependent}_Close"])
        fitted = row.intercept + row.beta*np.log(prices[f"{row.independent}_Close"])
        ax.plot(y.index, y, linewidth=1, label=f"log {row.dependent}")
        ax.plot(y.index, fitted, linewidth=1, label=f"fitted on {row.independent}")
        ax.set_title(f"{row.pair_id}: {row.dependent} on {row.independent}", fontsize=9)
        ax.set_ylabel("Natural log Close")
        ax.legend(fontsize=7)
        ax.tick_params(axis="x", rotation=30, labelsize=8)
    save(fig, "pair_fits.png")

    fig, axes = panels("Selected-direction residuals | 2018-2025 | fitted in sample")
    for ax, row in zip(axes, rows.itertuples(), strict=True):
        ax.plot(spreads.index, spreads[row.spread_column], linewidth=.8)
        ax.axhline(0, color="black", linewidth=.6)
        ax.set_title(f"{row.spread_column} | {row.evidence_label}", fontsize=9)
        ax.set_ylabel("Log-price residual")
        ax.tick_params(axis="x", rotation=30, labelsize=8)
    save(fig, "residual_histories.png")

    ranked = tables["pair_ranking"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 8), layout="constrained", sharey=True)
    y = np.arange(len(ranked))
    for col, label, marker in [("eg_pvalue", "Selected direction", "o"), ("holm_pair_pvalue", "Pair Holm", "x")]:
        axes[0].scatter(np.maximum(ranked[col], np.finfo(float).tiny), y, label=label, marker=marker)
    axes[0].axvline(cfg["alpha"], color="black", linestyle="--", linewidth=1, label="5%")
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Engle-Granger p-value (log scale)")
    axes[0].set_yticks(y, [f"{r.pair_id} ({r.evidence_label})" for r in ranked.itertuples()])
    axes[0].invert_yaxis()
    axes[0].legend()
    axes[1].scatter(ranked.trace_stat_r0-ranked.trace_critical_r0_95, y, label="rank 0")
    axes[1].scatter(ranked.trace_stat_r1-ranked.trace_critical_r1_95, y, marker="x", label="rank at most 1")
    axes[1].axvline(0, color="black", linestyle="--", linewidth=1)
    axes[1].set_xlabel("Johansen trace statistic minus 95% critical value")
    axes[1].legend()
    fig.suptitle("Pair evidence in ranking order | nominal tests and pair-level adjustment")
    save(fig, "method_comparison.png")

    fig, ax = plt.subplots(figsize=(12, 8), layout="constrained")
    stability = tables["hedge_stability"]
    y = np.arange(len(rows))
    for offset, period in zip([-.15, .15], cfg["stability_periods"], strict=True):
        values = stability[stability.period == period["name"]].set_index("pair_id").loc[rows.pair_id, "beta"]
        ax.barh(y+offset, values, height=.28, label=period["name"].replace("_", "-"))
    ax.set_yticks(y, rows.spread_column)
    ax.invert_yaxis()
    ax.axvline(0, color="black", linewidth=.7)
    ax.set_xlabel("OLS slope on log prices (dimensionless)")
    ax.set_title("Hedge-ratio comparison in the fixed selected direction")
    ax.legend()
    save(fig, "hedge_stability.png")
    return paths
