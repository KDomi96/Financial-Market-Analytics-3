"""Run the saved-input sentiment study independently of Phases 1-5."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from market_analytics.sentiment.evaluation import evaluate_benchmarks, prepare_benchmarks
from market_analytics.sentiment.model import FinBERT, file_hash, read_settings, save_json
from market_analytics.sentiment.headlines import clean_snapshot, pilot_report, validate_news_manifest


def run_benchmarks(root, settings, model=None):
    prepared, report = prepare_benchmarks(root, settings)
    print("Prepared benchmark counts:", {key: value["counts"] for key, value in report["datasets"].items()}, flush=True)
    model = model or FinBERT(root, settings)
    result = evaluate_benchmarks(root, settings, model, prepared)
    record = {
        "stage": "benchmarks", "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "fit": "none; unchanged local FinBERT checkpoint, fixed rules",
        "benchmark_snapshot": settings["benchmark_snapshot"],
        "model_revision": settings["model"]["revision"],
        "settings": settings,
        "versions": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                     for name in ["numpy", "pandas", "torch", "transformers", "scikit-learn", "vaderSentiment"]}},
        "source_hashes": report["source_hashes"],
        "code_hashes": {path.relative_to(root).as_posix(): file_hash(path)
                        for path in (root / "src/market_analytics/sentiment").glob("*.py")},
        "lock_sha256": file_hash(root / "uv.lock"),
    }
    save_json(root / settings["paths"]["metrics"] / "benchmark_run.json", record)
    return result


def daily_table(scored, manifest, settings, sessions):
    rows = []
    session_strings = sorted(day.isoformat() for day in sessions)
    for ticker in settings["companies"]:
        dates = pd.date_range(settings["start_date"], settings["end_date"]).strftime("%Y-%m-%d").tolist()
        direct, next_session_failed, next_session_capped = {}, set(), set()
        for date in dates:
            windows = [row for row in manifest["windows"] if row["ticker"] == ticker
                       and row["start"] <= date <= row["end"] and row["status"] != "split"]
            complete = bool(windows) and all(row["status"] in {"success", "capped"} for row in windows)
            capped = any(row["status"] == "capped" for row in windows)
            direct[date] = complete, capped
            # Missing after-close items could belong to the following session.
            next_day = next((day for day in session_strings if day > date), None)
            if next_day and not complete:
                next_session_failed.add(next_day)
            if next_day and capped:
                next_session_capped.add(next_day)
        for date in dates:
            direct_complete, direct_capped = direct[date]
            complete = direct_complete and date not in next_session_failed
            subset = scored.loc[(scored.ticker == ticker) & (scored.analysis_date == date)]
            rows.append({"ticker": ticker, "date": date, "headline_count": len(subset) if complete else pd.NA,
                         "observed_headline_count": len(subset),
                         "mean_score": float(subset.score.mean()) if len(subset) and complete else np.nan,
                         "date_only_share": float(subset.date_only.mean()) if len(subset) else np.nan,
                         "direct_request_complete": direct_complete,
                         "source_timing_gap": date in next_session_failed or date in next_session_capped,
                         "request_complete": complete, "capped": direct_capped or date in next_session_capped})
    result = pd.DataFrame(rows)
    result["headline_count"] = result.headline_count.astype("Int64")
    return result


def weekly_table(daily, supported_companies):
    frame = daily.copy()
    frame["week_end"] = pd.to_datetime(frame.date).dt.to_period("W-FRI").dt.end_time.dt.strftime("%Y-%m-%d")
    rows = []
    for (ticker, week_end), group in frame.groupby(["ticker", "week_end"], sort=True):
        complete = bool(group.request_complete.all())
        capped = bool(group.capped.any())
        observed = int(group.observed_headline_count.sum())
        count = int(group.headline_count.sum()) if complete else None
        mean = float((group.mean_score.fillna(0) * group.observed_headline_count).sum() / observed) if observed and complete else np.nan
        partial = len(group) != 7
        rows.append({"ticker": ticker, "week_end": week_end, "headline_count": count,
                     "observed_headline_count": observed, "mean_score": mean,
                     "request_complete": complete, "capped": capped, "partial_study_week": partial,
                     "sparse_pilot_coverage": ticker not in supported_companies,
                     "comparison_eligible": complete and not capped and not partial and ticker in supported_companies and observed > 0})
    result = pd.DataFrame(rows)
    result["headline_count"] = result.headline_count.astype("Int64")
    return result


def weekly_returns(root, settings):
    # Market prices are used only for this saved-return comparison, never to select news.
    columns = ["Date"] + [f"{ticker}_Return" for ticker in settings["companies"]]
    master = pd.read_csv(root / settings["paths"]["market_master"], usecols=columns)
    if master.Date.duplicated().any() or not master.Date.between(settings["start_date"], settings["end_date"]).all():
        raise ValueError("Unexpected market comparison dates")
    master["week_end"] = pd.to_datetime(master.Date).dt.to_period("W-FRI").dt.end_time.dt.strftime("%Y-%m-%d")
    rows = []
    for ticker in settings["companies"]:
        for week_end, group in master.groupby("week_end"):
            returns = group[f"{ticker}_Return"]
            if returns.isna().any():
                raise ValueError("Missing market return in the comparison")
            rows.append({"ticker": ticker, "week_end": week_end,
                         "weekly_return": float((1 + returns / 100).prod() - 1), "trading_sessions": len(group)})
    return pd.DataFrame(rows)


def market_comparisons(root, settings, scored, daily, weekly, zscores):
    metrics = root / settings["paths"]["metrics"]
    joined = weekly.merge(weekly_returns(root, settings), on=["ticker", "week_end"], validate="one_to_one")
    associations = []
    for ticker, group in joined.groupby("ticker"):
        valid = group.loc[group.comparison_eligible].dropna(subset=["mean_score", "weekly_return"])
        coefficient = float(spearmanr(valid.mean_score, valid.weekly_return).statistic) if len(valid) > 2 else np.nan
        associations.append({"ticker": ticker, "weeks": len(valid),
                             "spearman": coefficient if np.isfinite(coefficient) else np.nan,
                             "interpretation": "descriptive association; no predictive or causal claim"})
    joined.to_csv(metrics / "weekly_market_comparison.csv", index=False)
    pd.DataFrame(associations).to_csv(metrics / "weekly_return_associations.csv", index=False)
    pairs = zscores[["pair_id", "dependent", "independent"]].drop_duplicates()
    differences = []
    for pair in pairs.itertuples(index=False):
        dep = weekly.loc[(weekly.ticker == pair.dependent) & weekly.comparison_eligible, ["week_end", "mean_score"]]
        ind = weekly.loc[(weekly.ticker == pair.independent) & weekly.comparison_eligible, ["week_end", "mean_score"]]
        comparison = dep.merge(ind, on="week_end", suffixes=("_dependent", "_independent"), validate="one_to_one")
        comparison["pair_id"] = pair.pair_id
        comparison["score_difference"] = comparison.mean_score_dependent - comparison.mean_score_independent
        differences.append(comparison)
    difference_frame = pd.concat(differences, ignore_index=True)
    difference_frame.to_csv(metrics / "weekly_pair_differences.csv", index=False)
    signals = pd.read_csv(root / settings["paths"]["signals"])
    eligible = signals.eligible_long.astype(str).str.lower().eq("true") | signals.eligible_short.astype(str).str.lower().eq("true")
    events, sessions = [], sorted(zscores.Date.unique())
    for signal in signals.loc[eligible].itertuples(index=False):
        previous = [day for day in sessions if day < signal.Date][-5:]
        for ticker in [signal.dependent, signal.independent]:
            subset = scored.loc[(scored.ticker == ticker) & scored.analysis_date.isin(previous)]
            coverage = daily.loc[(daily.ticker == ticker) & daily.date.isin(previous)]
            complete = len(previous) == 5 and len(coverage) == 5 and bool(coverage.request_complete.all())
            capped = bool(coverage.capped.any())
            today = daily.loc[(daily.ticker == ticker) & (daily.date == signal.Date)].iloc[0]
            events.append({"pair_id": signal.pair_id, "signal_date": signal.Date,
                           "direction": "long" if str(signal.eligible_long).lower() == "true" else "short", "ticker": ticker,
                           "lookback_sessions": ";".join(previous), "lookback_complete": complete, "lookback_capped": capped,
                           "prior_five_session_count": len(subset) if complete else None,
                           "prior_five_session_mean_score": float(subset.score.mean()) if len(subset) and complete else np.nan,
                           "signal_day_count": int(today.headline_count) if pd.notna(today.headline_count) else None,
                           "signal_day_complete": bool(today.request_complete), "signal_day_capped": bool(today.capped)})
    pd.DataFrame(events).to_csv(metrics / "entry_signal_context.csv", index=False)
    return associations, difference_frame, events


def figures(root, settings, daily, weekly, differences, zscores, benchmark_results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory = root / settings["paths"]["figures"]
    directory.mkdir(parents=True, exist_ok=True)
    for column, ylabel, filename in [("mean_score", "Mean model score", "weekly_sentiment.png"),
                                     ("observed_headline_count", "Retrieved headlines", "weekly_coverage.png")]:
        fig, axes = plt.subplots(3, 2, figsize=(12, 10), sharex=True)
        for ax, ticker in zip(axes.flat, settings["companies"]):
            frame = weekly.loc[weekly.ticker == ticker]
            ax.plot(pd.to_datetime(frame.week_end), frame[column], marker=".", linewidth=1)
            ax.set_title(ticker + (" (sparse coverage)" if frame.sparse_pilot_coverage.any() else ""))
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.2)
            if column == "mean_score":
                ax.axhline(0, color="black", linewidth=0.5)
                ax.set_ylim(-1, 1)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(directory / filename, dpi=150)
        plt.close(fig)
    for pair_id, group in zscores.groupby("pair_id"):
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(pd.to_datetime(group.Date), group.zscore, color="black", label="Phase 4 Z-score")
        ax.set_ylabel("Z-score")
        other = ax.twinx()
        frame = differences.loc[differences.pair_id == pair_id]
        other.plot(pd.to_datetime(frame.week_end), frame.score_difference, color="tab:blue", marker=".", label="Weekly score difference")
        other.set_ylabel("Dependent minus independent news score")
        ax.set_title(f"{pair_id}: weekly news score difference and Z-score (exploratory)")
        ax.legend(loc="upper left")
        other.legend(loc="upper right")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(directory / f"{pair_id}_news_and_zscore.png", dpi=150)
        plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(11, 7))
    for i, (dataset, result) in enumerate(benchmark_results.items()):
        for j, (name, metric) in enumerate(result["models"].items()):
            ax = axes[i, j]
            matrix = np.array(metric["confusion_matrix"])
            ax.imshow(matrix, cmap="Greys")
            for (a, b), count in np.ndenumerate(matrix):
                ax.text(b, a, str(count), ha="center", va="center", color="white" if count > matrix.max() / 2 else "black")
            ax.set_xticks(range(3), metric["label_order"], rotation=30)
            ax.set_yticks(range(3), metric["label_order"])
            ax.set_title(f"{dataset}: {name}")
            ax.set_xlabel("Predicted")
            ax.set_ylabel("Gold")
    fig.tight_layout()
    fig.savefig(directory / "benchmark_confusion_matrices.png", dpi=150)
    plt.close(fig)


def run_study(root, settings):
    if not settings["news_snapshot"] or not settings["pilot_snapshot"]:
        raise ValueError("Select saved pilot and full news snapshots in the settings")
    zscores = pd.read_csv(root / settings["paths"]["zscores"])
    sessions = sorted(pd.to_datetime(zscores.Date).dt.date.unique())
    pilot = pilot_report(root, settings, root / settings["pilot_snapshot"], sessions)
    if not pilot["passed"]:
        raise ValueError("The selected pilot has not passed")
    cleaned, excluded, manifest = clean_snapshot(root, settings, root / settings["news_snapshot"], sessions)
    validate_news_manifest(manifest, settings, pilot=False)
    if manifest["status"] not in {"complete", "partial"}:
        raise ValueError("Finish collection attempts before scoring the news")
    model = FinBERT(root, settings)
    benchmarks = run_benchmarks(root, settings, model)
    print(f"Scoring {len(cleaned)} retained news headlines", flush=True)
    score_columns = ["p_positive", "p_negative", "p_neutral", "predicted_label", "score", "token_count", "truncated"]
    scored = pd.concat([cleaned.reset_index(drop=True), pd.DataFrame(model.score(cleaned.text.tolist()), columns=score_columns)], axis=1)
    interim = root / settings["paths"]["interim"]
    cleaned.to_csv(interim / "news_cleaned.csv", index=False)
    excluded.to_csv(interim / "news_excluded.csv", index=False)
    scored.to_csv(interim / "news_scored.csv", index=False)
    daily = daily_table(scored, manifest, settings, sessions)
    weekly = weekly_table(daily, pilot["supported_companies"])
    processed = root / settings["paths"]["processed"]
    processed.mkdir(parents=True, exist_ok=True)
    daily.to_csv(processed / "daily_sentiment.csv", index=False)
    weekly.to_csv(processed / "weekly_sentiment.csv", index=False)
    metrics = root / settings["paths"]["metrics"]
    excluded.groupby(["ticker", "reason"]).size().rename("count").to_csv(metrics / "news_exclusion_counts.csv")
    scored.groupby(["ticker", "publisher"]).size().rename("count").to_csv(metrics / "news_publisher_counts.csv")
    scored.assign(month=scored.reported_date.str[:7]).groupby(["ticker", "month"]).size().rename("count").to_csv(metrics / "news_monthly_counts.csv")
    associations, differences, events = market_comparisons(root, settings, scored, daily, weekly, zscores)
    figures(root, settings, daily, weekly, differences, zscores, benchmarks)
    complete = manifest["status"] == "complete" and set(scored.ticker) == set(settings["companies"])
    record = {"status": "complete" if complete else "partial", "finished_at_utc": datetime.now(timezone.utc).isoformat(),
              "settings": settings, "lock_sha256": file_hash(root / "uv.lock"),
              "benchmark_manifest_sha256": file_hash(root / settings["benchmark_snapshot"] / "manifest.json"),
              "news_manifest_sha256": file_hash(root / settings["news_snapshot"] / "manifest.json"),
              "pilot_manifest_sha256": file_hash(root / settings["pilot_snapshot"] / "manifest.json"),
              "model_manifest_sha256": file_hash(root / settings["model"]["directory"] / "../model_revision.json"),
              "market_inputs": {settings["paths"][key]: file_hash(root / settings["paths"][key]) for key in ["market_master", "zscores", "signals"]},
              "kept_headlines": len(scored), "excluded_items": len(excluded),
              "kept_from_split_windows": {ticker: int(count) for ticker, count
                                          in scored.groupby("ticker").split_window.sum().items()},
              "date_only_headlines": int(scored.date_only.sum()), "truncated_headlines": int(scored.truncated.sum()),
              "daily_rows": len(daily), "weekly_rows": len(weekly), "signal_stock_rows": len(events),
              "collection_status": manifest["status"], "associations": associations,
              "code_hashes": {path.relative_to(root).as_posix(): file_hash(path)
                              for path in (root / "src/market_analytics/sentiment").glob("*.py")}}
    # Undefined correlations are recorded as null, not nonstandard JSON NaN values.
    record["associations"] = [{key: (None if isinstance(value, float) and not np.isfinite(value) else value)
                               for key, value in item.items()} for item in associations]
    save_json(metrics / "run_metadata.json", record)
    print(json.dumps({key: record[key] for key in ["kept_headlines", "excluded_items", "kept_from_split_windows", "date_only_headlines", "daily_rows", "weekly_rows", "signal_stock_rows"]}), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/sentiment.json"))
    parser.add_argument("--stage", choices=["benchmarks", "all"], default="all")
    args = parser.parse_args()
    root, settings = read_settings(args.config)
    if args.stage == "all":
        run_study(root, settings)
    else:
        run_benchmarks(root, settings)
