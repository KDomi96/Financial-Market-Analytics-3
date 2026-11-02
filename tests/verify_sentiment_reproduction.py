"""Compare saved sentiment runs and check the earlier phases' file contracts."""

import argparse
import json
from pathlib import Path
import re
import subprocess

import numpy as np
import pandas as pd

from market_analytics.sentiment.model import file_hash, save_json

CONTINUOUS = {"score", "mean_score", "date_only_share", "mean", "vader_compound", "weekly_return",
              "spearman", "score_difference", "mean_score_dependent", "mean_score_independent",
              "prior_five_session_mean_score"}


def contract_hashes(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, item in value.items():
        if isinstance(item, str) and "/" in key and re.fullmatch(r"[a-f0-9]{64}", item):
            result[key] = item
        elif isinstance(item, dict):
            result.update(contract_hashes(item))
    return result


def frozen_checks(root):
    baseline_path = root / ".tools/sentiment_handoff_manifest.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {}
    changed = [relative for relative, expected in baseline.items() if file_hash(root / relative) != expected]
    contracts = {}
    for relative in ["outputs/metrics/statistical_baseline/phase4_v1/evaluation_contract.json",
                     "outputs/metrics/lstm/phase5_v2/evaluation_contract.json"]:
        saved = json.loads((root / relative).read_text(encoding="utf-8"))
        hashes = contract_hashes(saved)
        contracts[relative] = {"checked": len(hashes), "changed": [name for name, expected in hashes.items()
                                                                  if file_hash(root / name) != expected]}
    phase5 = json.loads((root / "outputs/metrics/lstm/phase5_v2/evaluation_contract.json").read_text(encoding="utf-8"))
    frozen = ["src/market_analytics/" + name for name in ["trading", "features", "models", "cointegration", "data/master.py"]]
    # Unlike a plain diff, status also reports staged and untracked files.
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *frozen],
                            capture_output=True, text=True, check=True, cwd=root)
    return {"handoff_inventory_present": baseline_path.exists(), "handoff_files_checked": len(baseline), "handoff_files_changed": changed, "contracts": contracts,
            "frozen_code_diff": [line[3:] for line in status.stdout.splitlines()],
            "phase5_lock_mismatch_expected": file_hash(root / "uv.lock") != phase5["signature"]["lock_sha256"]}


def compare(reference, actual):
    report = {"csv_files": [], "json_files": [], "errors": [], "probability_tolerance": 1e-5,
              "max_probability_difference": 0.0, "max_continuous_difference": 0.0}
    for group in ["interim", "processed", "metrics"]:
        for path in sorted((reference / group).glob("*.csv")):
            other = actual / group / path.name
            relative = f"{group}/{path.name}"
            if not other.exists():
                report["errors"].append(f"Missing {relative}")
                continue
            left, right = pd.read_csv(path), pd.read_csv(other)
            if list(left.columns) != list(right.columns) or len(left) != len(right):
                report["errors"].append(f"Schema/row mismatch: {relative}")
                continue
            for column in left:
                probabilities = column.startswith("p_")
                if probabilities or column in CONTINUOUS:
                    a = pd.to_numeric(left[column], errors="raise").to_numpy(dtype=float)
                    b = pd.to_numeric(right[column], errors="raise").to_numpy(dtype=float)
                    valid = np.isfinite(a) & np.isfinite(b)
                    maximum = float(np.abs(a[valid] - b[valid]).max()) if valid.any() else 0.0
                    key = "max_probability_difference" if probabilities else "max_continuous_difference"
                    report[key] = max(report[key], maximum)
                    if not np.allclose(a, b, atol=1e-5, rtol=0, equal_nan=True):
                        report["errors"].append(f"Numeric mismatch: {relative}:{column}")
                elif not left[column].equals(right[column]):
                    report["errors"].append(f"Discrete/count/exclusion mismatch: {relative}:{column}")
            report["csv_files"].append({"file": relative, "rows": len(left)})
    for filename in ["benchmark_preparation.json", "fiqa_metrics.json", "finentity_metrics.json", "pilot_report.json"]:
        left = json.loads((reference / "metrics" / filename).read_text(encoding="utf-8"))
        right = json.loads((actual / "metrics" / filename).read_text(encoding="utf-8"))
        left_numeric = left.pop("numeric_diagnostics", None)
        right_numeric = right.pop("numeric_diagnostics", None)
        equal = left == right
        diagnostics_equal, maximum = True, 0.0
        if left_numeric is not None or right_numeric is not None:
            if left_numeric is None or right_numeric is None or left_numeric.keys() != right_numeric.keys():
                diagnostics_equal = False
            else:
                for key, value in left_numeric.items():
                    other = right_numeric[key]
                    if isinstance(value, (int, float)) and isinstance(other, (int, float)):
                        difference = abs(value - other)
                        maximum = max(maximum, difference)
                        diagnostics_equal &= difference <= 1e-5
                    else:
                        diagnostics_equal &= value == other
        report["json_files"].append({"file": filename, "exact": equal,
                                    "numeric_diagnostics_within_tolerance": bool(diagnostics_equal),
                                    "max_numeric_diagnostic_difference": maximum})
        if not equal:
            report["errors"].append(f"JSON metrics differ: {filename}")
        if not diagnostics_equal:
            report["errors"].append(f"Numeric diagnostics exceed tolerance: {filename}")
    left = json.loads((reference / "metrics/run_metadata.json").read_text(encoding="utf-8"))
    right = json.loads((actual / "metrics/run_metadata.json").read_text(encoding="utf-8"))
    fixed_keys = ["settings", "lock_sha256", "benchmark_manifest_sha256", "news_manifest_sha256", "pilot_manifest_sha256",
                  "model_manifest_sha256", "market_inputs", "code_hashes", "kept_headlines", "excluded_items",
                  "kept_from_split_windows",
                  "date_only_headlines", "truncated_headlines", "daily_rows", "weekly_rows", "signal_stock_rows", "collection_status"]
    for key in fixed_keys:
        if left[key] != right[key]:
            report["errors"].append(f"Run contract differs: {key}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    report = compare(args.reference, args.actual)
    report["frozen"] = frozen_checks(root)
    frozen = report["frozen"]
    unchanged = not frozen["handoff_files_changed"] and not frozen["frozen_code_diff"] and all(
        not value["changed"] for value in frozen["contracts"].values())
    report["passed"] = not report["errors"] and unchanged
    report["reference"] = args.reference.as_posix()
    report["actual"] = args.actual.as_posix()
    report["validator_sha256"] = file_hash(Path(__file__))
    save_json(args.report, report)
    print(json.dumps({key: report[key] for key in ["passed", "max_probability_difference", "max_continuous_difference", "errors"]}, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
