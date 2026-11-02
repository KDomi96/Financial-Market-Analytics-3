"""Prepare the two labeled datasets and evaluate the frozen classifiers."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import unicodedata
import zipfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from market_analytics.sentiment.model import file_hash, save_json, vader_label

LABELS = ["negative", "neutral", "positive"]
FIELDS = {"fiqa": ("sentence", "info"), "finentity": ("content", "annotations")}
# PhraseBank's shortest entries are greetings and fragments that occur in
# ordinary text, so an entry this short counts only when the whole record equals it.
MINIMUM_CONTAINED_TOKENS = 5


def normalized_text(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def phrasebank_overlap(text, normalized_sentences):
    normalized = normalized_text(text)
    padded = f" {normalized} "
    return any(sentence == normalized or (sentence.count(" ") + 1 >= MINIMUM_CONTAINED_TOKENS
                                          and f" {sentence} " in padded)
               for sentence in normalized_sentences)


def annotation_identity(dataset, annotation):
    if dataset == "fiqa":
        return annotation["target"], float(annotation["sentiment_score"])
    return annotation["value"], annotation["label"]


def texts_with_several_annotations(dataset, records):
    """Normalized texts whose records together carry more than one distinct annotation.

    FiQA can list a headline again under a new ID for a second target, so a
    record with one annotation can still belong to a multi-target text.
    """
    text_key, annotation_key = FIELDS[dataset]
    found = defaultdict(set)
    for row in records:
        found[normalized_text(row[text_key])].update(
            annotation_identity(dataset, annotation) for annotation in row[annotation_key])
    return {text for text, identities in found.items() if len(identities) > 1}


def fiqa_label(score):
    if not np.isfinite(score) or not -1 <= score <= 1:
        raise ValueError("Invalid FiQA score")
    return "negative" if score < -0.3 else "positive" if score > 0.3 else "neutral"


def checked_snapshot(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "complete":
        raise ValueError("Benchmark snapshot is incomplete")
    for item in manifest["records"]:
        if file_hash(directory / item["file"]) != item["sha256"]:
            raise ValueError(f"Benchmark source changed: {item['file']}")
    return manifest


def prepare_benchmarks(root, settings):
    snapshot = root / settings["benchmark_snapshot"]
    manifest = checked_snapshot(snapshot)
    archive_path = snapshot / "financial_phrasebank/FinancialPhraseBank-v1.0.zip"
    with zipfile.ZipFile(archive_path) as archive:
        source_name = next(name for name in archive.namelist() if name.endswith("/Sentences_50Agree.txt"))
        phrases = [line.rsplit("@", 1)[0] for line in archive.read(source_name).decode("latin-1").splitlines()]
    normalized_phrases = sorted(set(map(normalized_text, phrases)))
    interim = root / settings["paths"]["interim"]
    interim.mkdir(parents=True, exist_ok=True)
    summaries, prepared, exclusions = {}, {}, []
    for dataset, relative in [("fiqa", "fiqa/task1_headline_ABSA_train.json"),
                              ("finentity", "finentity/FinEntity.json")]:
        data = json.loads((snapshot / relative).read_text(encoding="utf-8"))
        items = list(data.items() if isinstance(data, dict) else enumerate(data))
        several = texts_with_several_annotations(dataset, [row for _, row in items])
        text_key, annotation_key = FIELDS[dataset]
        rows, seen, counts = [], set(), Counter()
        for key, row in items:
            record_id = f"{dataset}_{key}"
            text, annotations = row[text_key], row[annotation_key]
            normalized = normalized_text(text)
            counts["source_rows"] += 1
            reason = None
            if len(annotations) != 1 or normalized in several:
                reason = "multiple_annotations"
            elif dataset == "finentity" and text[annotations[0]["start"]:annotations[0]["end"]] != annotations[0]["value"]:
                reason = "span_value_mismatch"
            elif normalized in seen:
                reason = "duplicate_text"
            elif phrasebank_overlap(text, normalized_phrases):
                reason = "phrasebank_overlap"
            if reason:
                counts[reason] += 1
                exclusions.append({"dataset": dataset, "record_id": record_id, "reason": reason})
                continue
            seen.add(normalized)
            annotation = annotations[0]
            numeric = float(annotation["sentiment_score"]) if dataset == "fiqa" else None
            label = fiqa_label(numeric) if dataset == "fiqa" else annotation["label"].lower()
            if label not in LABELS:
                raise ValueError("Unexpected benchmark gold label")
            rows.append({"record_id": record_id, "text": text, "gold_label": label,
                         "gold_score": numeric, "target": annotation["target" if dataset == "fiqa" else "value"]})
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise ValueError(f"No prepared rows for {dataset}")
        counts["retained"] = len(rows)
        counts["excluded"] = counts["source_rows"] - counts["retained"]
        summaries[dataset] = {"counts": dict(counts), "class_counts": dict(sorted(Counter(frame.gold_label).items()))}
        frame.to_csv(interim / f"{dataset}_prepared.csv", index=False)
        prepared[dataset] = frame
    test = json.loads((snapshot / "fiqa/task1_headline_ABSA_test.json").read_text(encoding="utf-8"))
    summaries["fiqa"]["unlabeled_test_rows_excluded"] = len(test)
    for key in test:
        exclusions.append({"dataset": "fiqa", "record_id": f"fiqa_test_{key}", "reason": "unlabeled_test"})
    overlap = set(map(normalized_text, prepared["fiqa"].text)) & set(map(normalized_text, prepared["finentity"].text))
    report = {"datasets": summaries, "phrasebank_sentences": len(phrases), "cross_benchmark_equal_texts": len(overlap),
              "normalization": ("NFKC, casefold, Unicode word tokens joined by spaces; equality, or containment at "
                                f"token boundaries for entries of at least {MINIMUM_CONTAINED_TOKENS} tokens"),
              "source_hashes": {item["file"]: item["sha256"] for item in manifest["records"]}}
    pd.DataFrame(exclusions).to_csv(interim / "benchmark_exclusions.csv", index=False)
    save_json(root / settings["paths"]["metrics"] / "benchmark_preparation.json", report)
    return prepared, report


def metrics(gold, predicted, seed, n_bootstrap):
    gold, predicted = np.asarray(gold), np.asarray(predicted)
    if not len(gold) or len(gold) != len(predicted):
        raise ValueError("Metric inputs must be nonempty and aligned")
    if set(gold) - set(LABELS) or set(predicted) - set(LABELS):
        raise ValueError("Unexpected metric label")
    rng = np.random.default_rng(seed)
    intervals = np.empty((n_bootstrap, 2))
    for i in range(n_bootstrap):
        index = rng.integers(0, len(gold), size=len(gold))
        intervals[i] = (accuracy_score(gold[index], predicted[index]),
                        f1_score(gold[index], predicted[index], labels=LABELS, average="macro", zero_division=0))
    return {"rows": len(gold), "accuracy": float(accuracy_score(gold, predicted)),
            "macro_f1": float(f1_score(gold, predicted, labels=LABELS, average="macro", zero_division=0)),
            "label_order": LABELS, "confusion_matrix": confusion_matrix(gold, predicted, labels=LABELS).tolist(),
            "classification_report": classification_report(gold, predicted, labels=LABELS, output_dict=True, zero_division=0),
            "bootstrap": {"seed": seed, "samples": n_bootstrap, "method": "paired row resampling; fixed three-class macro-F1",
                          "accuracy_95": np.quantile(intervals[:, 0], [0.025, 0.975]).tolist(),
                          "macro_f1_95": np.quantile(intervals[:, 1], [0.025, 0.975]).tolist()}}


def evaluate_benchmarks(root, settings, model, prepared):
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    analyzer = SentimentIntensityAnalyzer()
    directory = root / settings["paths"]["metrics"]
    directory.mkdir(parents=True, exist_ok=True)
    evaluation = settings["evaluation"]
    results = {}
    for dataset, frame in prepared.items():
        print(f"Scoring {dataset}: {len(frame)} prepared records", flush=True)
        predictions = pd.DataFrame(model.score(frame.text.tolist()))
        scored = pd.concat([frame.reset_index(drop=True), predictions], axis=1)
        scored["vader_compound"] = [analyzer.polarity_scores(text)["compound"] for text in frame.text]
        scored["vader_label"] = scored.vader_compound.map(vader_label)
        majority = sorted(Counter(frame.gold_label).items(), key=lambda item: (-item[1], LABELS.index(item[0])))[0][0]
        result = {"class_counts": dict(sorted(Counter(frame.gold_label).items())), "majority_class": majority,
                  "truncated_rows": int(scored.truncated.sum()), "models": {}}
        for name, labels in [("finbert", scored.predicted_label), ("vader", scored.vader_label),
                             ("majority", [majority] * len(frame))]:
            result["models"][name] = metrics(frame.gold_label, labels, evaluation["seed"], evaluation["bootstrap_samples"])
        if dataset == "fiqa":
            difference = scored.score.to_numpy() - frame.gold_score.to_numpy()
            correlation = float(spearmanr(scored.score, frame.gold_score).statistic)
            result["numeric_diagnostics"] = {"mae": float(np.abs(difference).mean()),
                                              "rmse": float(np.sqrt((difference ** 2).mean())),
                                              "spearman": correlation if np.isfinite(correlation) else None,
                                              "note": "Classifier score is not calibrated to FiQA regression targets"}
        scored.to_csv(root / settings["paths"]["interim"] / f"{dataset}_scored.csv", index=False)
        scored.loc[scored.predicted_label != scored.gold_label,
                   ["record_id", "gold_label", "predicted_label", "score", "vader_label"]].to_csv(
                       directory / f"{dataset}_disagreements.csv", index=False)
        save_json(directory / f"{dataset}_metrics.json", result)
        results[dataset] = result
        print(f"{dataset}: macro-F1 FinBERT={result['models']['finbert']['macro_f1']:.4f}, "
              f"VADER={result['models']['vader']['macro_f1']:.4f}, majority={result['models']['majority']['macro_f1']:.4f}", flush=True)
    return results
