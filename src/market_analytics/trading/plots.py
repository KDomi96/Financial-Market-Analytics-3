"""Draw the baseline figures from its dated tables."""

import matplotlib.pyplot as plt
import pandas as pd


def save_figures(tables, cfg, directory):
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for kind in ("zscores", "equity", "drawdown"):
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), layout="constrained")
        for ax, pair in zip(axes, cfg["pairs"]):
            pair_id = pair["pair_id"]
            z = tables["zscores"].loc[lambda x: x["pair_id"].eq(pair_id)]
            daily = tables["daily_account"].loc[lambda x: x["pair_id"].eq(pair_id)]
            signals = tables["signals"].loc[lambda x: x["pair_id"].eq(pair_id)]
            fills = tables["executions"].loc[lambda x: x["pair_id"].eq(pair_id) & x["leg"].eq("dependent")]
            dates = pd.to_datetime(z["Date"])
            if kind == "zscores":
                ax.plot(dates, z["zscore"], lw=1, label="Fixed Z-score")
                for level in (-2, 0, 2):
                    ax.axhline(level, color="0.5", lw=.7, ls="--")
                for column, marker, label in (("eligible_long", "^", "Long signal"),
                                               ("eligible_short", "v", "Short signal"),
                                               ("exit_signal", "x", "Exit signal")):
                    selected = signals.loc[signals[column]]
                    ax.scatter(pd.to_datetime(selected["Date"]), selected["zscore"], marker=marker, s=40, label=label)
                lookup = z.set_index("Date")["zscore"]
                ax.scatter(pd.to_datetime(fills["Date"]), fills["Date"].map(lookup),
                           marker="o", s=45, facecolors="none", edgecolors="black", label="Next-open fill date")
                if z["period"].iloc[0] == "historical":
                    ax.axvspan(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"),
                               alpha=.12, color="grey", label="Normalization window")
                ax.set_ylabel("Z-score")
            else:
                for cost_type in ("gross", "net"):
                    column = f"{cost_type}_equity" if kind == "equity" else f"{cost_type}_drawdown"
                    ax.plot(pd.to_datetime(daily["Date"]), daily[column], label=cost_type.capitalize(), lw=1.2)
                ax.set_ylabel("Account equity (USD)" if kind == "equity" else "Drawdown (fraction)")
            label = "in sample" if z["period"].iloc[0] == "historical" else "unseen"
            ax.set_title(f"{pair['dependent']} on {pair['independent']} | exploratory | {label}")
            ax.legend(loc="best", fontsize=8, ncol=3)
            ax.grid(alpha=.2)
            ax.set_xlabel("Trading date")
        path = directory / f"{kind}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths
