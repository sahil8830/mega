"""Create a clearly attributed Codex-reviewed copy of the blank audit sheet."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EDA = ROOT / "runs" / "eda"


def main():
    source = EDA / "modality_label_audit.tsv"
    destination = EDA / "modality_label_audit_codex.tsv"
    review = json.loads((EDA / "codex_query_intent_labels.json").read_text())
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, dialect="excel-tab")
        rows, fieldnames = list(reader), list(reader.fieldnames)
    fieldnames.append("reviewer_type")
    labels = review["labels"]
    if set(labels) != {row["audit_id"] for row in rows}:
        raise ValueError("Review labels and audit IDs do not match exactly")
    for row in rows:
        label, confidence, notes = labels[row["audit_id"]]
        row.update(human_label=label, human_confidence=confidence,
                   reviewer_notes=notes, reviewer_type=review["reviewer_type"])
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)
    print(destination)


if __name__ == "__main__":
    main()
