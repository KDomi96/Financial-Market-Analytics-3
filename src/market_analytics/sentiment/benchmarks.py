"""Download the sentiment benchmarks without changing their source records."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import urllib.request
import zipfile


def describe_data(body: bytes, kind: str) -> dict:
    """Check source fields and count records without preparing evaluation rows."""
    if kind == "financial_phrasebank_zip":
        counts = {}
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            for name in archive.namelist():
                if Path(name).name.startswith("Sentences_") and name.endswith(".txt"):
                    lines = archive.read(name).decode("latin-1").splitlines()
                    for line in lines:
                        sentence, label = line.rsplit("@", 1)
                        if not sentence.strip() or label not in {"positive", "negative", "neutral"}:
                            raise ValueError("Invalid PhraseBank sentence or label")
                    counts[Path(name).name] = len(lines)
        if counts.get("Sentences_50Agree.txt") != 4846:
            raise ValueError("Unexpected PhraseBank 50%-agreement count")
        return {"sentence_files": counts, "role": "overlap screen only; never scored"}
    data = json.loads(body)
    rows = list(data.values()) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a non-empty dataset")
    fiqa = kind.startswith("fiqa_")
    text_key, annotation_key = ("sentence", "info") if fiqa else ("content", "annotations")
    texts, annotation_counts, scores, labels = [], [], [], Counter()
    span_value_mismatches = 0
    for row in rows:
        text, annotations = row[text_key], row[annotation_key]
        if not isinstance(text, str) or not text.strip() or not isinstance(annotations, list) or not annotations:
            raise ValueError("Missing source text or annotations")
        texts.append(text)
        annotation_counts.append(len(annotations))
        for annotation in annotations:
            if fiqa:
                if not annotation.get("target") or not annotation.get("snippets"):
                    raise ValueError("Missing FiQA target or snippet")
                has_score = "sentiment_score" in annotation
                if has_score != (kind == "fiqa_labeled"):
                    raise ValueError("FiQA score availability differs from the configured file role")
                if has_score:
                    score = float(annotation["sentiment_score"])
                    if not math.isfinite(score) or not -1 <= score <= 1:
                        raise ValueError("FiQA score is outside [-1, 1]")
                    scores.append(score)
            else:
                label = annotation["tag"]
                if label not in {"Positive", "Negative", "Neutral"} or annotation["label"] != label:
                    raise ValueError("Unexpected FinEntity label")
                start, end = annotation["start"], annotation["end"]
                if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text):
                    raise ValueError("Invalid FinEntity entity span")
                span_value_mismatches += text[start:end] != annotation["value"]
                labels[label] += 1
    result = {
        "rows": len(rows),
        "annotations": sum(annotation_counts),
        "single_annotation_rows": annotation_counts.count(1),
        "exact_duplicate_text_rows": len(texts) - len(set(texts)),
    }
    if fiqa:
        result.update({"labeled_annotations": len(scores), "score_range": [min(scores), max(scores)] if scores else None})
    else:
        result.update({"label_counts": dict(sorted(labels.items())), "span_value_mismatches": span_value_mismatches})
    return result


def download_snapshot(config_path: Path) -> Path:
    """Save pinned source files unchanged and record hashes and source checks."""
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    settings_bytes = config_path.read_bytes()
    settings = json.loads(settings_bytes)
    started = datetime.now(timezone.utc)
    run_dir = project_root / settings["output_directory"] / started.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "status": "interrupted",
        "started_at_utc": started.isoformat(),
        "python_version": platform.python_version(),
        "config": config_path.relative_to(project_root).as_posix(),
        "config_sha256": hashlib.sha256(settings_bytes).hexdigest(),
        "acquisition_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "representation": "HTTP response bodies saved unchanged; no filtering or scoring",
        "datasets": {key: {k: v for k, v in value.items() if k != "files"} for key, value in settings["datasets"].items()},
        "records": [],
    }
    try:
        for dataset, source in settings["datasets"].items():
            directory = run_dir / dataset
            directory.mkdir()
            for item in source["files"]:
                request = urllib.request.Request(item["url"], headers={"User-Agent": "market-analytics-research"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read()
                    final_url = response.geturl()
                    content_type = response.headers.get("Content-Type")
                if not body:
                    raise ValueError(f"Empty response for {item['name']}")
                path = directory / item["name"]
                path.write_bytes(body)
                record = {
                    "dataset": dataset,
                    "file": path.relative_to(run_dir).as_posix(),
                    "url": item["url"],
                    "final_url": final_url,
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "content_type": content_type,
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
                manifest["records"].append(record)
                if kind := item.get("validation"):
                    record["validation_kind"] = kind
                    record["source_summary"] = describe_data(body, kind)
                print(f"{record['file']}: {record['bytes']} bytes", flush=True)
        manifest["status"] = "complete"
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Snapshot: {run_dir.relative_to(project_root).as_posix()}", flush=True)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/sentiment_benchmarks.json"))
    args = parser.parse_args()
    download_snapshot(args.config)
