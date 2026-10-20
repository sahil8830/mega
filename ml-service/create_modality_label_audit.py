"""Create a deterministic human-audit sheet for generated modality labels.

The sheet samples the validation split across query cue types and subtitle
availability. It never assigns human labels automatically.
"""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from app.services.modality_classifier import _VISUAL_KEYWORDS
from generate_qvh_labels import _OCR_PATTERNS, _SPEECH_PATTERNS

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "moment_detr"
OUT = ROOT / "runs" / "eda" / "modality_label_audit.tsv"
QUOTAS = {"ocr": 13, "mixed": 22, "speech": 22, "visual": 22, "none": 21}
FIELDNAMES = (
    "audit_id", "split", "qid", "vid", "query", "relevant_windows",
    "subtitle_status", "subtitle_file_count", "cue_bucket", "proxy_label",
    "visual_score", "speech_score", "ocr_score", "human_label",
    "human_confidence", "reviewer_notes",
)


def has_match(patterns, text):
    return any(re.search(pattern, text) for pattern in patterns)


def cue_bucket(query):
    text = query.lower()
    hits = {
        "visual": has_match(_VISUAL_KEYWORDS, text),
        "speech": has_match(_SPEECH_PATTERNS, text),
        "ocr": has_match(_OCR_PATTERNS, text),
    }
    active = [name for name, present in hits.items() if present]
    return active[0] if len(active) == 1 else ("mixed" if active else "none")


def stable_order(row):
    return hashlib.sha256(f"modality-audit-v1:{row['qid']}".encode()).hexdigest()


def choose_balanced(rows, count):
    """Take a stable sample while representing both subtitle groups."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["subtitle_status"]].append(row)
    for values in groups.values():
        values.sort(key=stable_order)
    selected = []
    names = ("with_subtitles", "without_subtitles")
    while len(selected) < count and any(groups.values()):
        for name in names:
            if groups[name] and len(selected) < count:
                selected.append(groups[name].pop(0))
    return selected


def main():
    annotations = [json.loads(line) for line in
                   (SOURCE / "data/highlight_val_release.jsonl").read_text().splitlines()
                   if line.strip()]
    subtitle_counts = Counter(
        path.stem[3:].rsplit("_subs", 1)[0]
        for path in (SOURCE / "features/clip_sub_features").glob("qid*.npz")
        if path.stem.startswith("qid")
    )
    with np.load(ROOT / "data/qvhighlights_val.npz", allow_pickle=False) as data:
        scores = data["modality_scores"]
        labels = data["soft_labels"].argmax(axis=1)
        embeddings = data["query_embs"]
    if len(annotations) != len(scores):
        raise ValueError("Validation annotations and generated arrays have different lengths")

    candidates = defaultdict(list)
    names = ("visual", "speech", "ocr")
    for index, annotation in enumerate(annotations):
        query_file = SOURCE / f"features/clip_text_features/qid{annotation['qid']}.npz"
        with np.load(query_file, allow_pickle=False) as source:
            expected = source["pooler_output"].astype(np.float32).reshape(-1)
        expected /= np.linalg.norm(expected) + 1e-8
        if not np.allclose(expected, embeddings[index], atol=1e-6, rtol=1e-5):
            raise ValueError(f"Generated row alignment failed at qid {annotation['qid']}")
        subtitle_count = subtitle_counts[annotation["vid"]]
        row = {
            **annotation,
            "subtitle_status": "with_subtitles" if subtitle_count else "without_subtitles",
            "subtitle_file_count": subtitle_count,
            "cue_bucket": cue_bucket(annotation["query"]),
            "proxy_label": names[int(labels[index])],
            "scores": scores[index],
        }
        candidates[row["cue_bucket"]].append(row)

    selected = []
    for bucket, quota in QUOTAS.items():
        if len(candidates[bucket]) < quota:
            raise ValueError(f"Only {len(candidates[bucket])} {bucket} candidates for quota {quota}")
        selected.extend(choose_balanced(candidates[bucket], quota))
    selected.sort(key=lambda row: (list(QUOTAS).index(row["cue_bucket"]), stable_order(row)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, dialect="excel-tab")
        writer.writeheader()
        for audit_id, row in enumerate(selected, 1):
            writer.writerow({
                "audit_id": f"A{audit_id:03d}", "split": "val", "qid": row["qid"],
                "vid": row["vid"], "query": row["query"],
                "relevant_windows": json.dumps(row["relevant_windows"], separators=(",", ":")),
                "subtitle_status": row["subtitle_status"],
                "subtitle_file_count": row["subtitle_file_count"], "cue_bucket": row["cue_bucket"],
                "proxy_label": row["proxy_label"],
                "visual_score": f"{row['scores'][0]:.6f}",
                "speech_score": f"{row['scores'][1]:.6f}",
                "ocr_score": f"{row['scores'][2]:.6f}",
                "human_label": "", "human_confidence": "", "reviewer_notes": "",
            })
    summary = {
        "rows": len(selected),
        "cue_buckets": Counter(row["cue_bucket"] for row in selected),
        "subtitle_status": Counter(row["subtitle_status"] for row in selected),
        "proxy_labels": Counter(row["proxy_label"] for row in selected),
        "proxy_by_subtitle_status": {
            status: Counter(row["proxy_label"] for row in selected
                            if row["subtitle_status"] == status)
            for status in ("with_subtitles", "without_subtitles")
        },
    }
    print(json.dumps(summary, indent=2))
    print(OUT)


if __name__ == "__main__":
    main()
