"""Validate a completed modality audit sheet and calculate proxy-label quality."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

LABELS = ("visual", "speech", "ocr", "mixed", "unclear")
CORE = ("visual", "speech", "ocr")


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path, nargs="?", default=Path("runs/eda/modality_label_audit.tsv"))
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("runs/eda/modality_label_audit_results.json"))
    args = parser.parse_args()
    with args.sheet.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, dialect="excel-tab"))
    invalid = [row["audit_id"] for row in rows if row["human_label"] and row["human_label"] not in LABELS]
    if invalid:
        raise ValueError(f"Invalid human_label in rows: {', '.join(invalid)}")
    invalid_confidence = [row["audit_id"] for row in rows
                          if row["human_confidence"] and row["human_confidence"] not in ("high", "medium", "low")]
    if invalid_confidence:
        raise ValueError(f"Invalid human_confidence in rows: {', '.join(invalid_confidence)}")
    missing_confidence = [row["audit_id"] for row in rows
                          if row["human_label"] and not row["human_confidence"]]
    if missing_confidence:
        raise ValueError(f"Labeled rows missing human_confidence: {', '.join(missing_confidence)}")
    completed = [row for row in rows if row["human_label"]]
    if len(completed) != len(rows) and not args.allow_incomplete:
        raise ValueError(f"Audit incomplete: {len(completed)}/{len(rows)} labeled. Use --allow-incomplete for progress.")
    confusion = {actual: {predicted: 0 for predicted in CORE} for actual in LABELS}
    for row in completed:
        confusion[row["human_label"]][row["proxy_label"]] += 1
    per_class = {}
    for label in CORE:
        tp = confusion[label][label]
        actual = sum(confusion[label].values())
        predicted = sum(confusion[a][label] for a in LABELS)
        precision, recall = safe_div(tp, predicted), safe_div(tp, actual)
        # A supported class that is never predicted has zero F1. A class with
        # no audited support remains unmeasured and is excluded from macro F1.
        if not actual:
            f1 = None
        elif not predicted or not tp:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        per_class[label] = {"support": actual, "precision": precision, "recall": recall, "f1": f1}
    scorable = [row for row in completed if row["human_label"] in CORE]
    report = {
        "total_rows": len(rows), "completed_rows": len(completed),
        "reviewer_types": Counter(row.get("reviewer_type") or "independent_human"
                                  for row in completed),
        "review_label_counts": Counter(row["human_label"] for row in completed),
        "exact_agreement_all_labels": safe_div(sum(row["proxy_label"] == row["human_label"] for row in completed), len(completed)),
        "three_class_accuracy": safe_div(sum(row["proxy_label"] == row["human_label"] for row in scorable), len(scorable)),
        "macro_f1": safe_div(sum(v["f1"] for v in per_class.values() if v["f1"] is not None),
                             sum(v["f1"] is not None for v in per_class.values())),
        "per_class": per_class, "confusion_matrix": confusion,
        "agreement_by_subtitle_status": {
            status: safe_div(sum(r["proxy_label"] == r["human_label"] for r in completed if r["subtitle_status"] == status),
                             sum(r["subtitle_status"] == status for r in completed))
            for status in ("with_subtitles", "without_subtitles")
        },
        "note": "Mixed and unclear rows are excluded from three-class accuracy and macro F1.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
