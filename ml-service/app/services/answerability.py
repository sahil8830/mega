"""
Phase 4 - Answerability Detection.

Determines whether the retrieved results are actually relevant to the query,
or whether the system should say "no matching video found".

Three signals combined:
  1. Score gap:        top score vs tail score -> large gap = confident match
  2. Absolute score:   top score must exceed a minimum threshold
  3. Modality agreement: at least 2 modalities agree on the top result

Output:
  {
    "answerable": True/False,
    "confidence": 0.0–1.0,
    "reason": "high_confidence" | "low_score" | "low_gap" | "modality_disagreement"
  }
"""
from __future__ import annotations

import numpy as np
from typing import List, Dict, Any


# ─── Thresholds ───────────────────────────────────────────────────────────────

# Minimum fused score for the top result to be considered relevant.
# CLIP cosine similarities typically range 0.15-0.35 for relevant matches.
# Set low so single-topic corpora (all chunks related) don't get filtered.
MIN_TOP_SCORE = 0.10

# Minimum gap between top and median score.
# In a single-topic corpus all chunks score similarly, so gap is tiny.
# Set very low to avoid false "unanswerable" responses.
MIN_SCORE_GAP = 0.01

# Modality agreement: at least 1 modality must score above threshold
MIN_MODALITY_AGREEMENT = 1
MODALITY_AGREE_THRESH  = 0.10


def compute_answerability(
    results: List[Dict[str, Any]],
    visual_scores: List[float] | None = None,
    speech_scores: List[float] | None = None,
    ocr_scores:    List[float] | None = None,
    min_top_score: float = MIN_TOP_SCORE,
    min_gap:       float = MIN_SCORE_GAP,
) -> Dict[str, Any]:
    """
    Given a ranked list of search results, determine if the query is answerable.

    Args:
        results:       List of result dicts with 'score' key (sorted desc)
        visual_scores: Raw visual FAISS scores for top results
        speech_scores: Raw speech FAISS scores for top results
        ocr_scores:    Raw OCR FAISS scores for top results
        min_top_score: Minimum fused score threshold
        min_gap:       Minimum gap between top and median score

    Returns:
        Dict with keys: answerable, confidence, reason, top_score, score_gap
    """
    if not results:
        return {
            "answerable": False,
            "confidence": 0.0,
            "reason":     "no_results",
            "top_score":  0.0,
            "score_gap":  0.0,
        }

    scores = [r.get("score", 0.0) for r in results]
    top_score = scores[0]

    # ── Signal 1: Absolute top score ─────────────────────────────────────────
    if top_score < min_top_score:
        return {
            "answerable": False,
            "confidence": _normalize(top_score, 0, min_top_score),
            "reason":     "low_score",
            "top_score":  round(top_score, 4),
            "score_gap":  0.0,
        }

    # ── Signal 2: Score gap (top vs median) ──────────────────────────────────
    if len(scores) >= 3:
        median_score = float(np.median(scores[1:]))   # median of non-top results
        score_gap = top_score - median_score
    elif len(scores) == 2:
        score_gap = top_score - scores[1]
    else:
        score_gap = top_score   # only one result -> gap = top score itself

    if score_gap < min_gap:
        return {
            "answerable": False,
            "confidence": _normalize(score_gap, 0, min_gap) * 0.8,
            "reason":     "low_gap",
            "top_score":  round(top_score, 4),
            "score_gap":  round(score_gap, 4),
        }

    # ── Signal 3: Modality agreement ─────────────────────────────────────────
    agreeing = 0
    if visual_scores and len(visual_scores) > 0 and visual_scores[0] > MODALITY_AGREE_THRESH:
        agreeing += 1
    if speech_scores and len(speech_scores) > 0 and speech_scores[0] > MODALITY_AGREE_THRESH:
        agreeing += 1
    if ocr_scores and len(ocr_scores) > 0 and ocr_scores[0] > MODALITY_AGREE_THRESH:
        agreeing += 1

    if visual_scores is not None and agreeing < MIN_MODALITY_AGREEMENT:
        return {
            "answerable": False,
            "confidence": 0.3,
            "reason":     "modality_disagreement",
            "top_score":  round(top_score, 4),
            "score_gap":  round(score_gap, 4),
        }

    # ── All signals passed: answerable ────────────────────────────────────────
    # Confidence = weighted combo of score + gap
    score_conf = _normalize(top_score, min_top_score, 1.0)
    gap_conf   = _normalize(score_gap, min_gap, 0.5)
    confidence = round(0.6 * score_conf + 0.4 * gap_conf, 3)
    confidence = min(1.0, confidence)

    return {
        "answerable": True,
        "confidence": confidence,
        "reason":     "high_confidence",
        "top_score":  round(top_score, 4),
        "score_gap":  round(score_gap, 4),
    }


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize value to [0, 1] between low and high."""
    if high <= low:
        return 1.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def filter_by_answerability(
    results: List[Dict[str, Any]],
    answerability: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    If not answerable, return empty list.
    If answerable, attach confidence to each result.
    """
    if not answerability["answerable"]:
        return []

    confidence = answerability["confidence"]
    for r in results:
        r["confidence"] = confidence
    return results
