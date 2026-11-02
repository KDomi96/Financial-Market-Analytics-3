"""Run every project pair through the API routes and save the single-pair verdicts for the report."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from market_analytics.api.main import create_app

FIT_END = "2025-12-31"
OUTPUT = "outputs/metrics/api/project_pair_verdicts.csv"


def project_verdicts(client, ranking, tolerance):
    """One row per pair, with the Phase 3 values beside the API's for the same fitting sessions."""
    rows = []
    for pair in client.get("/pairs").json()["pairs"]:
        sample = client.get(f"/samples/{pair['pair_id']}").content
        response = client.post("/analyze", files={"file": ("prices.csv", sample, "text/csv")},
                               data={"fit_end": FIT_END})
        response.raise_for_status()
        body = response.json()
        tests, johansen = body["tests"], body["tests"]["johansen"]
        saved = ranking.loc[pair["pair_id"]]
        counts = body["signal_counts"] or {}
        rows.append({
            "pair_id": pair["pair_id"], "phase3_rank": int(saved["rank"]),
            "phase3_label": saved["evidence_label"], "fit_end": FIT_END,
            "fit_sessions": body["fit"]["fit_sessions"], "later_sessions": body["fit"]["later_sessions"],
            "dependent": tests["kept_dependent"], "independent": tests["kept_independent"],
            "eg_pvalue": min(d["eg_pvalue"] for d in tests["directions"]),
            "eg_pair_pvalue": tests["eg_pair_pvalue"], "eg_pass": tests["eg_pass"],
            "trace_stat_r0": johansen["trace_stat_r0"], "trace_critical_r0_95": johansen["trace_critical_r0_95"],
            "trace_rank_95": johansen["trace_rank_95"], "johansen_pass": tests["johansen_pass"],
            "cointegrated": tests["cointegrated"], "phase3_holm_pair_pvalue": float(saved["holm_pair_pvalue"]),
            "i1_warnings": len(body["warnings"]),
            "long_entries": counts.get("long_entries"), "short_entries": counts.get("short_entries"),
            "exits": counts.get("exits"),
            "matches_phase3": bool(
                (tests["kept_dependent"], tests["kept_independent"]) == (saved["dependent"], saved["independent"])
                and np.allclose([tests["eg_pair_pvalue"], johansen["trace_stat_r0"], johansen["trace_stat_r1"]],
                                [saved["eg_pair_pvalue"], saved["trace_stat_r0"], saved["trace_stat_r1"]], **tolerance)
                and johansen["trace_rank_95"] == saved["trace_rank_95"]),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/api.json"))
    args = parser.parse_args()
    root = args.config.resolve().parent.parent
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    tolerance = json.loads((root / cfg["pair_selection_config"]).read_text(encoding="utf-8"))["tolerance"]
    ranking = pd.read_csv(root / cfg["pair_ranking"]).set_index("pair_id")
    with TestClient(create_app(args.config)) as client:
        table = project_verdicts(client, ranking, tolerance)
    if not table.matches_phase3.all():
        raise SystemExit(f"Disagreement with Phase 3: {table.loc[~table.matches_phase3, 'pair_id'].tolist()}")
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, lineterminator="\n")
    print(table[["pair_id", "phase3_rank", "eg_pair_pvalue", "trace_rank_95", "cointegrated"]].to_string(index=False))
    print(f"Saved {path}")
