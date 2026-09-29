"""
QVHighlights Label Generator — REAL DATA VERSION.

Uses the pre-extracted CLIP features from moment_detr_features.tar.gz:
  clip_features/      → (N, 512) CLIP visual embeddings per video (2-sec clips)
  clip_sub_features/  → subtitle CLIP embeddings
  clip_text_features/ → pre-computed query CLIP text embeddings

Ground truth labels come from:
  highlight_train_release.jsonl → query + relevant_windows (seconds)

Label construction:
  For each (query, gt_windows) pair:
    1. Load video's CLIP visual embeddings from clip_features/
    2. Find which 2-sec clip indices overlap with gt_windows
    3. Compute visual_score = max cosine_sim(query_emb, gt_clip_embs)
    4. Load subtitle emb from clip_sub_features/ for the same window
    5. Compute speech_score = cosine_sim(query_emb, subtitle_emb)
    6. Compute ocr_score = keyword heuristic
    7. Build soft label = temperature-softmax([v_score, s_score, o_score])

Output: ml-service/data/qvhighlights_train.npz
        ml-service/data/qvhighlights_val.npz

Usage:
  cd ml-service
  venv\\Scripts\\activate
  python generate_qvh_labels.py
  python generate_qvh_labels.py --max-samples 1000   # quick test run
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ─── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent
MOMENT_DETR  = REPO_ROOT / "moment_detr"
DATA_DIR     = MOMENT_DETR / "data"
FEAT_DIR     = MOMENT_DETR / "moment_detr_features" / "features"

CLIP_VISUAL_DIR  = FEAT_DIR / "clip_features"       # (N, 512) visual per video
CLIP_SUB_DIR     = FEAT_DIR / "clip_sub_features"    # subtitle embeddings
CLIP_TEXT_DIR    = FEAT_DIR / "clip_text_features"   # pre-computed query embs

TRAIN_ANN = DATA_DIR / "highlight_train_release.jsonl"
VAL_ANN   = DATA_DIR / "highlight_val_release.jsonl"

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)

CLIP_DURATION = 2.0   # each clip is 2 seconds

# Built once at startup to avoid globbing 329k files per-video
_SUB_INDEX: Dict[str, List[Path]] = {}


def _build_sub_index():
    """Pre-index subtitle files: vid → [path, path, ...]. Called once."""
    global _SUB_INDEX
    if _SUB_INDEX:
        return
    print("[Setup] Building subtitle file index (one-time scan of 329k files)...")
    for p in CLIP_SUB_DIR.glob("qid-*.npz"):
        # Filename: qid-{vid}_subs{N}.npz
        name = p.stem  # e.g. qid---a6qL3eL0c_210.0_360.0_subs0
        # Strip leading "qid-" and trailing "_subsN"
        inner = name[4:]  # ---a6qL3eL0c_210.0_360.0_subs0
        vid = "_subs".join(inner.split("_subs")[:-1])  # ---a6qL3eL0c_210.0_360.0
        _SUB_INDEX.setdefault(vid, []).append(p)
    print(f"[Setup] Subtitle index built: {len(_SUB_INDEX)} unique videos.")


# ─── OCR / Speech heuristics ──────────────────────────────────────────────────

_OCR_PATTERNS = [
    r"\bcode\b", r"\bscript\b", r"\btext on\b", r"\bscreen\b",
    r"\bslide\b", r"\bwrite\b", r"\btyp\w+\b", r"\bformula\b",
    r"\bequation\b", r"\bmath\b", r"\bsubtitle\b", r"\bcaption\b",
]
_SPEECH_PATTERNS = [
    r"\bexplains?\b", r"\bsays?\b", r"\bsaid\b", r"\btalk\w*\b",
    r"\bdiscuss\w*\b", r"\bnarrat\w+\b", r"\bpresent\w+\b",
    r"\bspeak\w*\b", r"\bvoice\b", r"\bmentions?\b", r"\bdescrib\w+\b",
]


def _ocr_signal(query: str) -> float:
    q = query.lower()
    return min(0.8, sum(0.25 for p in _OCR_PATTERNS if re.search(p, q)))


def _speech_signal(query: str) -> float:
    q = query.lower()
    return min(0.8, sum(0.25 for p in _SPEECH_PATTERNS if re.search(p, q)))


# ─── Feature Loading ──────────────────────────────────────────────────────────

def _load_clip_visual(vid: str) -> Optional[np.ndarray]:
    """Load (N, 512) CLIP visual features for a video. Returns None if missing."""
    path = CLIP_VISUAL_DIR / f"{vid}.npz"
    if not path.exists():
        return None
    d = np.load(path)
    feats = d["features"].astype(np.float32)   # (N, 512)
    # L2-normalize each clip embedding
    norms = np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8
    return feats / norms


def _load_clip_sub(vid: str) -> Optional[np.ndarray]:
    """
    Load subtitle CLIP embeddings for a video using the pre-built index.
    Returns stacked (M, 512) array, or None if no files found.
    """
    files = _SUB_INDEX.get(vid)
    if not files:
        return None

    all_feats = []
    for f in files:
        d = np.load(f)
        feats = d["features"].astype(np.float32)
        norms = np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8
        all_feats.append(feats / norms)

    return np.vstack(all_feats)   # (total_clips, 512)


def _windows_to_clip_ids(windows: List[List[float]]) -> List[int]:
    """Convert second-based windows to 2-sec clip indices."""
    clip_ids = set()
    for w_start, w_end in windows:
        id_start = int(w_start / CLIP_DURATION)
        id_end   = int(np.ceil(w_end / CLIP_DURATION))
        clip_ids.update(range(id_start, id_end))
    return sorted(clip_ids)


def _cosine_sim_max(query_emb: np.ndarray, clip_embs: np.ndarray) -> float:
    """Max cosine similarity between a query embedding and a set of clip embeddings."""
    if clip_embs.shape[0] == 0:
        return 0.0
    # query_emb: (512,)  clip_embs: (M, 512)
    q = query_emb / (np.linalg.norm(query_emb) + 1e-8)
    sims = clip_embs @ q   # (M,)
    return float(np.max(sims))


def _build_soft_label(
    visual_score: float,
    speech_score: float,
    ocr_score: float,
    temperature: float = 1.5,
) -> np.ndarray:
    """Temperature-scaled softmax → soft target label summing to 1."""
    scores = np.array([visual_score, speech_score, ocr_score], dtype=np.float32)
    scores = scores / temperature
    scores -= scores.max()
    exp_s = np.exp(scores)
    return exp_s / exp_s.sum()


# ─── Main Generation ──────────────────────────────────────────────────────────

def generate_labels(
    annotations: List[Dict],
    clip_encode_fn,
    max_samples: int,
    batch_size: int,
    split_name: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[Dict]]:
    """
    Build (query_emb, modality_scores, soft_label) for all samples.
    """
    samples = annotations[:max_samples]
    n = len(samples)
    print(f"\n[{split_name}] Processing {n} samples...")

    # ── Batch-encode all query texts with CLIP ───────────────────────────────
    queries = [s["query"] for s in samples]
    print(f"[{split_name}] CLIP-encoding {n} queries (batch={batch_size})...")
    query_embs_list = []
    for i in range(0, n, batch_size):
        batch = queries[i:i+batch_size]
        embs = clip_encode_fn(batch)           # (B, 512)
        embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8)
        query_embs_list.append(embs)
        done = min(i + batch_size, n)
        if done % 500 == 0 or done == n:
            print(f"  Encoded {done}/{n}...")

    query_embs_arr = np.vstack(query_embs_list).astype(np.float32)   # (N, 512)

    # ── Build per-sample modality scores and soft labels ─────────────────────
    modality_scores_list = []
    soft_labels_list     = []
    meta                 = []
    missing_visual       = 0
    missing_speech       = 0

    for i, sample in enumerate(samples):
        vid     = sample["vid"]
        query   = sample["query"]
        windows = sample.get("relevant_windows", [])
        q_emb   = query_embs_arr[i]

        # ── Visual score: real CLIP visual embeddings ─────────────────────
        visual_feats = _load_clip_visual(vid)      # (N, 512) or None
        if visual_feats is not None:
            clip_ids = _windows_to_clip_ids(windows)
            # Clamp to valid range
            clip_ids = [c for c in clip_ids if c < len(visual_feats)]
            if clip_ids:
                gt_visual_embs = visual_feats[clip_ids]    # (M, 512)
                visual_score = _cosine_sim_max(q_emb, gt_visual_embs)
            else:
                visual_score = 0.15
        else:
            visual_score = 0.20   # fallback
            missing_visual += 1

        # ── Speech score: subtitle CLIP embeddings ────────────────────────
        sub_feats = _load_clip_sub(vid)            # (N, 512) or None
        if sub_feats is not None:
            clip_ids = _windows_to_clip_ids(windows)
            clip_ids = [c for c in clip_ids if c < len(sub_feats)]
            if clip_ids:
                gt_sub_embs = sub_feats[clip_ids]
                speech_score = _cosine_sim_max(q_emb, gt_sub_embs)
            else:
                speech_score = _speech_signal(query) * 0.5
        else:
            speech_score = _speech_signal(query) * 0.5
            missing_speech += 1

        # ── OCR score: keyword heuristic (QVH is mostly non-text videos) ──
        ocr_score = max(0.05, _ocr_signal(query) * 0.5)

        # ── Soft label ────────────────────────────────────────────────────
        label = _build_soft_label(visual_score, speech_score, ocr_score)

        modality_scores_list.append([visual_score, speech_score, ocr_score])
        soft_labels_list.append(label)
        meta.append({
            "qid":   sample.get("qid", i),
            "query": query,
            "vid":   vid,
            "has_visual_feats": visual_feats is not None,
            "has_sub_feats":    sub_feats is not None,
        })

        if (i + 1) % 500 == 0 or (i + 1) == n:
            print(f"  Labels: {i+1}/{n} | missing_visual={missing_visual} "
                  f"missing_speech={missing_speech}")

    modality_scores = np.array(modality_scores_list, dtype=np.float32)
    soft_labels     = np.array(soft_labels_list,     dtype=np.float32)

    print(f"[{split_name}] Done.")
    print(f"  query_embs:      {query_embs_arr.shape}")
    print(f"  modality_scores: {modality_scores.shape}  "
          f"mean=[{modality_scores.mean(axis=0)}]")
    print(f"  soft_labels:     {soft_labels.shape}  "
          f"mean=[{soft_labels.mean(axis=0).round(3)}]")

    return query_embs_arr, modality_scores, soft_labels, meta


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main(args):
    # Validate feature dirs exist
    if not CLIP_VISUAL_DIR.exists():
        print(f"[ERROR] CLIP visual features not found at: {CLIP_VISUAL_DIR}")
        print(f"        Extract moment_detr_features.tar.gz first.")
        sys.exit(1)

    print(f"[Setup] CLIP visual features: {CLIP_VISUAL_DIR}")
    print(f"        Files: {len(list(CLIP_VISUAL_DIR.glob('*.npz')))}")
    print(f"[Setup] CLIP sub features:    {CLIP_SUB_DIR}")
    print(f"        Files: {len(list(CLIP_SUB_DIR.glob('*.npz')))}")

    # Pre-build subtitle index (scans 329k files once, O(N) not O(N*queries))
    _build_sub_index()

    # Load CLIP text encoder from our pipeline
    sys.path.insert(0, str(Path(__file__).parent))
    from app.services.clip_model import encode_texts as clip_encode


    # Load annotations
    print("\n[Setup] Loading annotations...")
    with open(TRAIN_ANN, encoding="utf-8") as f:
        train_anns = [json.loads(l) for l in f if l.strip()]
    with open(VAL_ANN, encoding="utf-8") as f:
        val_anns = [json.loads(l) for l in f if l.strip()]
    print(f"  Train: {len(train_anns)} | Val: {len(val_anns)}")

    # Generate train labels
    tr_embs, tr_scores, tr_labels, tr_meta = generate_labels(
        train_anns, clip_encode,
        max_samples=args.max_samples,
        batch_size=args.batch_size,
        split_name="TRAIN",
    )

    # Generate val labels
    val_embs, val_scores, val_labels, val_meta = generate_labels(
        val_anns, clip_encode,
        max_samples=min(args.max_samples, len(val_anns)),
        batch_size=args.batch_size,
        split_name="VAL",
    )

    # Save
    out_train = OUT_DIR / "qvhighlights_train.npz"
    out_val   = OUT_DIR / "qvhighlights_val.npz"

    np.savez_compressed(str(out_train),
        query_embs=tr_embs,
        modality_scores=tr_scores,
        soft_labels=tr_labels,
    )
    np.savez_compressed(str(out_val),
        query_embs=val_embs,
        modality_scores=val_scores,
        soft_labels=val_labels,
    )
    with open(OUT_DIR / "meta_train.json", "w") as f:
        json.dump(tr_meta[:200], f, indent=2)

    print(f"\n[DONE] Saved to ml-service/data/")
    print(f"  qvhighlights_train.npz : {len(tr_embs)} samples")
    print(f"  qvhighlights_val.npz   : {len(val_embs)} samples")
    print(f"\nNext:")
    print(f"  python train_weighting_module.py --data-dir data/ --epochs 200")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=9999999,
                        help="Limit samples (default: all). Use 100 for quick test.")
    parser.add_argument("--batch-size",  type=int, default=128,
                        help="CLIP encoding batch size")
    args = parser.parse_args()
    main(args)
