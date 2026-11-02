"""Download the pinned FinBERT files and score text without fitting."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

import numpy as np


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_settings(path=Path("configs/sentiment.json")):
    path = Path(path).resolve()
    settings = json.loads(path.read_text(encoding="utf-8"))
    thresholds = {"fiqa_negative_below": -0.3, "fiqa_positive_above": 0.3,
                  "vader_positive_at_least": 0.05, "vader_negative_at_most": -0.05}
    if any(settings["evaluation"].get(key) != value for key, value in thresholds.items()):
        raise ValueError("The adopted sentiment thresholds must remain fixed")
    return path.parent.parent, settings


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def download_model(config_path=Path("configs/sentiment.json")):
    root, settings = read_settings(config_path)
    model = settings["model"]
    if not re.fullmatch(r"[0-9a-f]{40}", model["revision"]):
        raise ValueError("Pin the model to a full commit revision")
    directory = root / model["directory"]
    manifest_path = directory.parent / "model_revision.json"
    # An interrupted download leaves its manifest behind; start that one again.
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "complete":
        verify_model(root, settings)
        print("Reusing verified model files", flush=True)
        return manifest_path
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"repository": model["repository"], "revision": model["revision"],
                "license": model["license"], "status": "interrupted", "files": []}
    try:
        for name in model["files"]:
            url = f"https://huggingface.co/{model['repository']}/resolve/{model['revision']}/{name}"
            path = directory / name
            temporary = path.with_suffix(path.suffix + ".part")
            request = urllib.request.Request(url, headers={"User-Agent": "market-analytics-research"})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as target:
                total = 0
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
                    total += len(chunk)
                    if name.endswith("safetensors") and total % (64 * 1024 * 1024) == 0:
                        print(f"{name}: {total // (1024 * 1024)} MiB", flush=True)
            if not total:
                raise ValueError(f"Empty model file: {name}")
            temporary.replace(path)
            manifest["files"].append({"file": name, "bytes": total, "sha256": file_hash(path),
                                      "url": url, "downloaded_at_utc": datetime.now(timezone.utc).isoformat()})
            print(f"{name}: {total} bytes", flush=True)
        label_names(json.loads((directory / "config.json").read_text(encoding="utf-8"))["id2label"])
        manifest["status"] = "complete"
    finally:
        save_json(manifest_path, manifest)
    return manifest_path


def verify_model(root, settings):
    directory = root / settings["model"]["directory"]
    record = json.loads((directory.parent / "model_revision.json").read_text(encoding="utf-8"))
    if record["status"] != "complete" or record["revision"] != settings["model"]["revision"]:
        raise ValueError("Model download is incomplete or the revision differs")
    if {item["file"] for item in record["files"]} != set(settings["model"]["files"]):
        raise ValueError("Model manifest file set differs")
    for item in record["files"]:
        if file_hash(directory / item["file"]) != item["sha256"]:
            raise ValueError(f"Model file changed: {item['file']}")
    return directory


def label_names(id2label):
    labels = {int(key): value.lower() for key, value in id2label.items()}
    if set(labels) != {0, 1, 2} or set(labels.values()) != {"positive", "negative", "neutral"}:
        raise ValueError("Expected exactly positive, negative, and neutral labels")
    return [labels[i] for i in range(3)]


def predictions(probabilities, id2label):
    labels = label_names(id2label)
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 2 or probabilities.shape[1] != 3:
        raise ValueError("Expected three class probabilities per row")
    if not np.isfinite(probabilities).all() or (probabilities < 0).any() or not np.allclose(probabilities.sum(axis=1), 1, atol=1e-6):
        raise ValueError("Invalid class probabilities")
    return [{**{f"p_{label}": float(row[i]) for i, label in enumerate(labels)},
             "predicted_label": labels[int(row.argmax())],
             "score": float(row[labels.index("positive")] - row[labels.index("negative")])}
            for row in probabilities]


class FinBERT:
    def __init__(self, root, settings):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.settings = settings["model"]
        directory = verify_model(root, settings)
        torch.set_num_threads(self.settings["cpu_threads"])
        torch.use_deterministic_algorithms(True)
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            directory, local_files_only=True, use_safetensors=True).to("cpu").eval()
        self.labels = self.model.config.id2label
        label_names(self.labels)

    def score(self, texts):
        results = []
        batch_size = self.settings["batch_size"]
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            lengths = [len(self.tokenizer(text, truncation=False)["input_ids"]) for text in batch]
            tokens = self.tokenizer(batch, padding=True, truncation=True,
                                    max_length=self.settings["max_length"], return_tensors="pt")
            with self.torch.inference_mode():
                probabilities = self.model(**tokens).logits.softmax(dim=-1).cpu().numpy()
            for row, length in zip(predictions(probabilities, self.labels), lengths):
                results.append({**row, "token_count": length, "truncated": length > self.settings["max_length"]})
        return results


def vader_label(compound):
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def main():
    parser = argparse.ArgumentParser(description="Download the pinned FinBERT files")
    parser.add_argument("--config", type=Path, default=Path("configs/sentiment.json"))
    args = parser.parse_args()
    print(download_model(args.config))
