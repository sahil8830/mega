"""Evaluate the saved weighting model against QVHighlights proxy labels.

This measures modality-label prediction, not video retrieval accuracy.
QVHighlights validation is labeled; the public test split has no ground truth.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from app.services.weighting_module import ModalityWeightingMLP, WEIGHTS_PATH


def load_data(path):
    with np.load(path) as data:
        return tuple(torch.from_numpy(data[key].astype(np.float32)) for key in
                     ("query_embs", "modality_scores", "soft_labels"))


def metrics(probs, labels):
    log_probs = probs.clamp_min(1e-8).log()
    targets = labels.argmax(1)
    predicted = probs.argmax(1)
    kl = F.kl_div(log_probs, labels, reduction="batchmean").item()
    ce = F.nll_loss(log_probs, targets).item()
    return {
        "combined_loss": 0.5 * (kl + ce),
        "kl_divergence": kl,
        "hard_label_cross_entropy": ce,
        "modality_label_accuracy": (predicted == targets).float().mean().item(),
        "mean_weights": probs.mean(0).tolist(),
        "per_modality": {
            name: {
                "examples": int((targets == index).sum()),
                "recall": (predicted[targets == index] == index).float().mean().item()
                if (targets == index).any() else None,
            } for index, name in enumerate(("visual", "speech", "ocr"))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("runs/qvh_full_evaluation.json"))
    args = parser.parse_args()
    torch.set_num_threads(4)
    train = load_data(args.data_dir / "qvhighlights_train.npz")
    q, scores, labels = load_data(args.data_dir / "qvhighlights_val.npz")
    model = ModalityWeightingMLP()
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True))
    model.eval()
    with torch.inference_mode():
        probs = model(q, scores)
    if not torch.isfinite(probs).all() or not torch.allclose(
            probs.sum(1), torch.ones(len(probs)), atol=1e-6):
        raise ValueError("Checkpoint produced invalid weights")
    report = {
        "checkpoint": WEIGHTS_PATH,
        "train_examples": len(train[0]),
        "validation_examples": len(q),
        "evaluation_split": "official QVHighlights validation",
        "dynamic": metrics(probs, labels),
        "equal_fixed_weights": metrics(torch.full_like(labels, 1 / 3), labels),
        "training_mean_fixed_weights": metrics(train[2].mean(0).expand_as(labels), labels),
        "limitations": [
            "Labels are derived from scores, rather than annotated modality importance.",
            "OCR scores use query keyword heuristics; subtitle evidence is video-level.",
            "No validation example has OCR as its dominant label; OCR performance is unmeasured.",
            "Validation chooses the best checkpoint and is not an independent test set.",
            "Retrieval Recall@K and temporal IoU have not been evaluated.",
            "Inference must use the same CLIP embedding space as the archive.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
