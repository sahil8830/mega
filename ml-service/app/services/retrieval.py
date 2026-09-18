"""
Multimodal Retrieval Service.

Handles FAISS search across all three modalities (visual, speech, OCR)
and fuses their scores into a single ranked result list.

Fixed-Weight Fusion (Phase 2 baseline):
  fused_score = w_visual * visual_sim + w_speech * speech_sim + w_ocr * ocr_sim

Where weights come from the modality classifier (default: 0.33 each).
The winning candidate list is deduplicated by segment_id and re-ranked.

Phase 3 will replace fixed weights with a learned dynamic weighting MLP.
"""
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

from app.services.clip_model import encode_texts
from app.services.faiss_manager import get_faiss_manager
from app.services.modality_classifier import classify_modality

# Default fixed weights (equal fusion baseline)
DEFAULT_WEIGHTS = {"visual": 0.33, "speech": 0.33, "ocr": 0.34}
TOP_K_PER_INDEX = 20   # retrieve more than needed, then fuse and re-rank
FINAL_TOP_K = 10       # return this many after fusion


def _search_one_embedding(
    query_emb: np.ndarray,
    index_type: str,
    top_k: int,
) -> List[Dict]:
    """Search a single FAISS index with one query embedding."""
    faiss_mgr = get_faiss_manager()
    return faiss_mgr.search(query_emb, index_type=index_type, top_k=top_k)


def _multi_query_search(
    rep_embeddings: np.ndarray,   # (K, 512)
    index_type: str,
    top_k: int,
) -> List[Dict]:
    """
    Search FAISS with multiple representative query embeddings.
    Merge results, keeping best score per segment_id.
    """
    best: Dict[str, Dict] = {}   # segment_id → best result dict

    for emb in rep_embeddings:
        results = _search_one_embedding(emb, index_type, top_k)
        for r in results:
            sid = r.get("segment_id", str(r.get("faiss_id")))
            if sid not in best or r["score"] > best[sid]["score"]:
                best[sid] = r

    return list(best.values())


def retrieve(
    query: str,
    representative_embeddings: Optional[np.ndarray] = None,
    modality_weights: Optional[Dict[str, float]] = None,
    top_k: int = FINAL_TOP_K,
) -> Dict:
    """
    Full retrieval pipeline for a user query.

    Args:
        query: Raw user query string.
        representative_embeddings: Pre-computed rep embeddings (K, 512).
            If None, the query itself is encoded as a single embedding.
        modality_weights: Dict {"visual": w, "speech": w, "ocr": w}.
            If None, modality classifier determines weights.
        top_k: Number of results to return.

    Returns:
        {
            "results": [
                {
                    "rank": int,
                    "segment_id": str,
                    "video_id": str,
                    "start_time": float,
                    "end_time": float,
                    "fused_score": float,
                    "visual_score": float,
                    "speech_score": float,
                    "ocr_score": float,
                    "modality_weights": {...},
                }, ...
            ],
            "modality": str,
            "weights": {...},
            "total_candidates": int,
        }
    """
    # ── Modality classification ─────────────────────────────────────────────
    modality_info = classify_modality(query)
    weights = modality_weights or modality_info["weights"]

    # ── Encode query if no pre-computed embeddings ──────────────────────────
    if representative_embeddings is None:
        embs = encode_texts([query])           # (1, 512)
        representative_embeddings = embs

    rep_embs = np.array(representative_embeddings, dtype=np.float32)

    # ── Search each index with all representative embeddings ────────────────
    visual_results = _multi_query_search(rep_embs, "visual", TOP_K_PER_INDEX)
    speech_results = _multi_query_search(rep_embs, "speech", TOP_K_PER_INDEX)
    ocr_results    = _multi_query_search(rep_embs, "ocr",    TOP_K_PER_INDEX)

    # ── Collect all segment_ids seen across modalities ─────────────────────
    all_sids = set(
        r.get("segment_id", str(r.get("faiss_id")))
        for results in [visual_results, speech_results, ocr_results]
        for r in results
    )

    # ── Build score maps per modality ───────────────────────────────────────
    def _score_map(results: List[Dict]) -> Dict[str, float]:
        return {
            r.get("segment_id", str(r.get("faiss_id"))): r["score"]
            for r in results
        }

    v_map = _score_map(visual_results)
    s_map = _score_map(speech_results)
    o_map = _score_map(ocr_results)

    # Build a metadata map (use first result that has the segment_id)
    meta_map: Dict[str, Dict] = {}
    for results in [visual_results, speech_results, ocr_results]:
        for r in results:
            sid = r.get("segment_id", str(r.get("faiss_id")))
            if sid not in meta_map:
                meta_map[sid] = r

    # ── Fixed-weight fusion ────────────────────────────────────────────────
    w_v = weights.get("visual", 0.33)
    w_s = weights.get("speech", 0.33)
    w_o = weights.get("ocr",    0.34)

    fused: List[Dict] = []
    for sid in all_sids:
        v_score = v_map.get(sid, 0.0)
        s_score = s_map.get(sid, 0.0)
        o_score = o_map.get(sid, 0.0)
        fused_score = w_v * v_score + w_s * s_score + w_o * o_score

        meta = meta_map.get(sid, {})
        fused.append({
            "segment_id":     sid,
            "video_id":       meta.get("video_id", ""),
            "chunk_id":       meta.get("chunk_id", -1),
            "start_time":     meta.get("start_time", 0.0),
            "end_time":       meta.get("end_time",   0.0),
            "fused_score":    round(float(fused_score), 6),
            "visual_score":   round(float(v_score), 6),
            "speech_score":   round(float(s_score), 6),
            "ocr_score":      round(float(o_score), 6),
            "modality_weights": weights,
        })

    # ── Sort by fused score descending ────────────────────────────────────
    fused.sort(key=lambda x: x["fused_score"], reverse=True)
    top_results = fused[:top_k]

    for i, r in enumerate(top_results):
        r["rank"] = i + 1

    return {
        "results":           top_results,
        "modality":          modality_info["modality"],
        "weights":           weights,
        "total_candidates":  len(all_sids),
        "query":             query,
    }
