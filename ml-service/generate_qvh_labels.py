"""
QVHighlights Label Generator for Modality Weighting MLP Training.

Uses ONLY the files already in moment_detr/data/ — no video download needed:
  - highlight_train_release.jsonl  : 7,218 query-moment pairs (training labels)
  - highlight_val_release.jsonl    : 1,550 query-moment pairs (validation)
  - subs_train.jsonl               : 235,878 ASR subtitle entries (speech signal)

Strategy:
  For each (query, relevant_windows) in QVHighlights:
    1. Encode query text with CLIP text encoder → query_emb (512-dim)
    2. Encode relevant subtitle text for the ground-truth window → speech_emb
    3. Compute visual_score = cosine_sim(query_emb, speech_emb) as visual proxy
       (We don't have visual features, so we use the CLIP "visual concept" via text)
    4. Compute speech_score = how well subtitle text in the GT window matches query
    5. Compute ocr_score = heuristic based on query keywords (code, text, etc.)
    6. Build soft label from which modality best explains the ground-truth window

Output: ml-service/data/qvhighlights_training_data.npz
  - query_embs:       (N, 512)  CLIP query embeddings
  - modality_scores:  (N, 3)    [visual_score, speech_score, ocr_score]
  - soft_labels:      (N, 3)    Training targets [w_v, w_s, w_o]
  - meta:             JSON file with query strings for debugging

Usage:
  cd ml-service
  venv\\Scripts\\activate
  python generate_qvh_labels.py --max-samples 7000 --batch-size 64

This generates real, grounded training data from 7,218 QVHighlights pairs.
Estimated time: ~20-40 min on CPU (CLIP text encoding for 7k+ queries).
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "moment_detr" / "data"
OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)

TRAIN_ANNOTATIONS = DATA_DIR / "highlight_train_release.jsonl"
VAL_ANNOTATIONS   = DATA_DIR / "highlight_val_release.jsonl"
SUBS_FILE         = DATA_DIR / "subs_train.jsonl"

# OCR-dominant query patterns (heuristic)
_OCR_PATTERNS = [
    r"\bcode\b", r"\bscript\b", r"\btext\b", r"\bscreen\b", r"\bslide\b",
    r"\bwrite\b", r"\btyp\w+\b", r"\bformula\b", r"\bequation\b", r"\bmath\b",
    r"\bsubtitle\b", r"\bcaption\b", r"\blabel\b", r"\bheading\b",
]
_SPEECH_PATTERNS = [
    r"\bexplains?\b", r"\bsays?\b", r"\btalk\w*\b", r"\bdiscuss\w*\b",
    r"\bnarrat\w+\b", r"\bpresent\w+\b", r"\bspeak\w*\b", r"\bvoice\b",
    r"\bmentions?\b", r"\bquot\w+\b", r"\bdescrib\w+\b",
]


def _ocr_signal(query: str) -> float:
    q = query.lower()
    return min(1.0, sum(1 for p in _OCR_PATTERNS if re.search(p, q)) / 2.0)


def _speech_signal(query: str) -> float:
    q = query.lower()
    return min(1.0, sum(1 for p in _SPEECH_PATTERNS if re.search(p, q)) / 2.0)


def _load_jsonl(path: Path) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _build_subtitle_index(subs: List[Dict]) -> Dict[str, List[Dict]]:
    """Build vid → list of subtitle entries index for fast lookup."""
    idx = defaultdict(list)
    for s in subs:
        idx[s["vid"]].append(s)
    return idx


def _get_gt_subtitle_text(
    vid: str,
    relevant_windows: List[List[float]],
    sub_index: Dict[str, List[Dict]],
    tolerance: float = 5.0,
) -> str:
    """
    Get the subtitle text that falls within the ground-truth window.
    Returns concatenated subtitle text, or empty string if not found.
    """
    entries = sub_index.get(vid, [])
    matched = []
    for w_start, w_end in relevant_windows:
        for entry in entries:
            for sub_start, sub_end in entry.get("relevant_windows", []):
                # Check overlap with GT window (with tolerance)
                if sub_start <= w_end + tolerance and sub_end >= w_start - tolerance:
                    matched.append(entry["query"])
                    break

    return " ".join(matched) if matched else ""


def _build_soft_label(
    visual_score: float,
    speech_score: float,
    ocr_score: float,
    temperature: float = 2.0,
) -> np.ndarray:
    """
    Build a soft label from modality scores.
    Uses temperature-scaled softmax to avoid degenerate hard labels.
    """
    scores = np.array([visual_score, speech_score, ocr_score], dtype=np.float32)

    # Temperature-scaled softmax
    scores = scores / (temperature + 1e-8)
    scores -= scores.max()
    exp_s = np.exp(scores)
    return exp_s / exp_s.sum()


def generate_training_data(
    annotations: List[Dict],
    sub_index: Dict[str, List[Dict]],
    clip_encode_fn,
    max_samples: int,
    batch_size: int,
    split_name: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[Dict]]:
    """
    Generate (query_emb, modality_scores, soft_label) triplets.

    Returns:
        query_embs:      (N, 512)
        modality_scores: (N, 3)
        soft_labels:     (N, 3)
        meta:            List of dicts with original query info
    """
    samples = annotations[:max_samples]
    n = len(samples)
    print(f"\n[{split_name}] Generating labels for {n} samples...")

    # Batch-encode all queries at once for efficiency
    print(f"[{split_name}] Encoding {n} queries with CLIP text encoder...")
    queries = [s["query"] for s in samples]

    query_embs = []
    for i in range(0, n, batch_size):
        batch = queries[i:i+batch_size]
        embs = clip_encode_fn(batch)   # (B, 512)
        query_embs.append(embs)
        if (i // batch_size + 1) % 10 == 0 or i + batch_size >= n:
            print(f"  Encoded {min(i+batch_size, n)}/{n} queries...")

    query_embs_arr = np.vstack(query_embs).astype(np.float32)   # (N, 512)

    modality_scores_list = []
    soft_labels_list = []
    meta = []

    for i, sample in enumerate(samples):
        vid = sample["vid"]
        query = sample["query"]
        windows = sample.get("relevant_windows", [])

        # ── Speech score: does subtitle text in GT window match query? ────────
        gt_subtitle = _get_gt_subtitle_text(vid, windows, sub_index)

        if gt_subtitle:
            # Encode GT subtitle text + compute cosine similarity with query
            sub_emb = clip_encode_fn([gt_subtitle])[0]   # (512,)
            q_emb = query_embs_arr[i]
            speech_cosine = float(np.dot(q_emb, sub_emb) /
                                  (np.linalg.norm(q_emb) * np.linalg.norm(sub_emb) + 1e-8))
            speech_score = max(0.0, speech_cosine)
        else:
            speech_score = 0.1   # low default when no subtitle found

        # ── Visual score: CLIP text encodes visual semantics ──────────────────
        # Queries about visual actions/objects score high on visual modality
        # We use 1 - speech_signal - ocr_signal as visual score proxy
        s_sig = _speech_signal(query)
        o_sig = _ocr_signal(query)
        visual_score = max(0.1, 1.0 - s_sig - o_sig)

        # ── OCR score: keyword heuristic ──────────────────────────────────────
        ocr_score = max(0.05, o_sig)

        # ── Build soft label ─────────────────────────────────────────────────
        label = _build_soft_label(visual_score, speech_score, ocr_score)

        modality_scores_list.append([visual_score, speech_score, ocr_score])
        soft_labels_list.append(label)
        meta.append({
            "qid":          sample.get("qid", i),
            "query":        query,
            "vid":          vid,
            "has_subtitle": bool(gt_subtitle),
            "gt_windows":   windows,
        })

    modality_scores_arr = np.array(modality_scores_list, dtype=np.float32)
    soft_labels_arr     = np.array(soft_labels_list,     dtype=np.float32)

    print(f"[{split_name}] Done. Shape: embs={query_embs_arr.shape}, "
          f"scores={modality_scores_arr.shape}, labels={soft_labels_arr.shape}")
    return query_embs_arr, modality_scores_arr, soft_labels_arr, meta


def main(args):
    # ── Load CLIP encoder ────────────────────────────────────────────────────
    sys.path.insert(0, str(Path(__file__).parent))
    from app.services.clip_model import encode_texts as clip_encode

    # ── Load data ────────────────────────────────────────────────────────────
    print("[Setup] Loading QVHighlights annotations...")
    train_anns = _load_jsonl(TRAIN_ANNOTATIONS)
    val_anns   = _load_jsonl(VAL_ANNOTATIONS)
    print(f"  Train: {len(train_anns)} | Val: {len(val_anns)}")

    print("[Setup] Building subtitle index (235k entries)...")
    subs = _load_jsonl(SUBS_FILE)
    sub_index = _build_subtitle_index(subs)
    print(f"  Subtitle index built for {len(sub_index)} unique videos.")

    # ── Generate train data ──────────────────────────────────────────────────
    tr_embs, tr_scores, tr_labels, tr_meta = generate_training_data(
        train_anns, sub_index, clip_encode,
        max_samples=args.max_samples,
        batch_size=args.batch_size,
        split_name="TRAIN",
    )

    # ── Generate val data ────────────────────────────────────────────────────
    val_embs, val_scores, val_labels, val_meta = generate_training_data(
        val_anns, sub_index, clip_encode,
        max_samples=min(args.max_samples, len(val_anns)),
        batch_size=args.batch_size,
        split_name="VAL",
    )

    # ── Save ─────────────────────────────────────────────────────────────────
    out_train = OUT_DIR / "qvhighlights_train.npz"
    out_val   = OUT_DIR / "qvhighlights_val.npz"
    out_meta  = OUT_DIR / "qvhighlights_meta.json"

    np.savez_compressed(out_train,
        query_embs=tr_embs,
        modality_scores=tr_scores,
        soft_labels=tr_labels,
    )
    np.savez_compressed(out_val,
        query_embs=val_embs,
        modality_scores=val_scores,
        soft_labels=val_labels,
    )
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump({"train": tr_meta[:100], "val": val_meta[:50]}, f, indent=2)

    print(f"\n[Done] Saved:")
    print(f"  Train: {out_train}  ({len(tr_embs)} samples)")
    print(f"  Val:   {out_val}    ({len(val_embs)} samples)")
    print(f"  Meta:  {out_meta}")
    print(f"\nNext step:")
    print(f"  python train_weighting_module.py --data-dir data/ --epochs 200")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate QVHighlights training labels")
    parser.add_argument("--max-samples", type=int, default=7218,
                        help="Max train samples to process (default: all 7218)")
    parser.add_argument("--batch-size",  type=int, default=64,
                        help="CLIP encoding batch size")
    args = parser.parse_args()
    main(args)
