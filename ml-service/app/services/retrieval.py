"""
Multimodal Retrieval Service.

Handles FAISS search across all three modalities (visual, speech, OCR)
and fuses their scores into a single ranked result list.

Two fusion modes:
  - Fixed-Weight (Phase 2 baseline): weights from modality classifier or user override
  - Dynamic-Weight (Phase 3):        weights from trained MLP conditioned on query + scores

Dynamic weighting is the CORE NOVEL CONTRIBUTION:
  query_emb → MLP(query_emb || top_scores) → [w_visual, w_speech, w_ocr]
  fused_score = w_v * visual_sim + w_s * speech_sim + w_o * ocr_sim
"""
from typing import Dict, List, Optional

import numpy as np

from app.services.clip_model import encode_texts
from app.services.faiss_manager import get_faiss_manager
from app.services.modality_classifier import classify_modality

# Phase 2 baseline equal-weight defaults
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
    best: Dict[str, Dict] = {}

    for emb in rep_embeddings:
        results = _search_one_embedding(emb, index_type, top_k)
        for r in results:
            sid = r.get("segment_id", str(r.get("faiss_id")))
            if sid not in best or r["score"] > best[sid]["score"]:
                best[sid] = r

    return list(best.values())


def _get_dynamic_weights(
    query_emb: np.ndarray,
    v_score: float,
    s_score: float,
    o_score: float,
) -> Dict[str, float]:
    """
    Compute dynamic per-query fusion weights using the trained MLP.
    Falls back to equal weights if model is untrained or throws.
    """
    from app.services.weighting_module import predict_weights
    modality_scores = np.array([v_score, s_score, o_score], dtype=np.float32)
    try:
        w = predict_weights(query_emb, modality_scores)
        return {"visual": float(w[0]), "speech": float(w[1]), "ocr": float(w[2])}
    except Exception as e:
        print(f"[Retrieval] Dynamic weighting failed: {e}. Falling back to equal weights.")
        return DEFAULT_WEIGHTS.copy()


def retrieve(
    query: str,
    representative_embeddings: Optional[np.ndarray] = None,
    modality_weights: Optional[Dict[str, float]] = None,
    top_k: int = FINAL_TOP_K,
    use_dynamic_weights: bool = False,
) -> Dict:
    """
    Full retrieval pipeline for a user query.

    Args:
        query: Raw user query string.
        representative_embeddings: Pre-computed rep embeddings (K, 512).
            If None, the query itself is encoded as a single embedding.
        modality_weights: Dict {"visual": w, "speech": w, "ocr": w}.
            Ignored when use_dynamic_weights=True.
        top_k: Number of results to return.
        use_dynamic_weights: If True, use the trained MLP weighting module
            (Phase 3). If False, use fixed weights from modality classifier
            (Phase 2 baseline).

    Returns:
        {
            "results": [...],
            "modality": str,
            "weights": {...},
            "total_candidates": int,
            "weighting_mode": "dynamic" | "fixed",
        }
    """
    # ── Modality classification (used for fallback + label) ─────────────────
    modality_info = classify_modality(query)

    # ── Encode query if no pre-computed embeddings ───────────────────────────
    if representative_embeddings is None:
        embs = encode_texts([query])           # (1, 512)
        representative_embeddings = embs

    rep_embs = np.array(representative_embeddings, dtype=np.float32)

    # ── Search each index with all representative embeddings ─────────────────
    visual_results = _multi_query_search(rep_embs, "visual", TOP_K_PER_INDEX)
    speech_results = _multi_query_search(rep_embs, "speech", TOP_K_PER_INDEX)
    ocr_results    = _multi_query_search(rep_embs, "ocr",    TOP_K_PER_INDEX)

    # ── Collect all segment_ids seen across modalities ────────────────────────
    all_sids = set(
        r.get("segment_id", str(r.get("faiss_id")))
        for results in [visual_results, speech_results, ocr_results]
        for r in results
    )

    # ── Build score maps per modality ─────────────────────────────────────────
    def _score_map(results: List[Dict]) -> Dict[str, float]:
        return {
            r.get("segment_id", str(r.get("faiss_id"))): r["score"]
            for r in results
        }

    v_map = _score_map(visual_results)
    s_map = _score_map(speech_results)
    o_map = _score_map(ocr_results)

    # Build a metadata map
    meta_map: Dict[str, Dict] = {}
    for results in [visual_results, speech_results, ocr_results]:
        for r in results:
            sid = r.get("segment_id", str(r.get("faiss_id")))
            if sid not in meta_map:
                meta_map[sid] = r

    # ── Determine fusion weights ───────────────────────────────────────────────
    weighting_mode = "fixed"
    if use_dynamic_weights:
        # Use the mean representative embedding as the query embedding for MLP
        query_emb_for_mlp = rep_embs.mean(axis=0)   # (512,)

        # Use the top candidate's scores as the "representative" modality scores
        top_v = max(v_map.values()) if v_map else 0.0
        top_s = max(s_map.values()) if s_map else 0.0
        top_o = max(o_map.values()) if o_map else 0.0

        weights = _get_dynamic_weights(query_emb_for_mlp, top_v, top_s, top_o)
        weighting_mode = "dynamic"
    elif modality_weights is not None:
        weights = modality_weights
    else:
        weights = modality_info["weights"]

    w_v = weights.get("visual", 0.33)
    w_s = weights.get("speech", 0.33)
    w_o = weights.get("ocr",    0.34)

    # ── Fixed-weight or dynamic fusion ─────────────────────────────────────────
    fused: List[Dict] = []
    for sid in all_sids:
        v_score = v_map.get(sid, 0.0)
        s_score = s_map.get(sid, 0.0)
        o_score = o_map.get(sid, 0.0)
        fused_score = w_v * v_score + w_s * s_score + w_o * o_score

        meta = meta_map.get(sid, {})
        fused.append({
            "segment_id":      sid,
            "video_id":        meta.get("video_id", ""),
            "chunk_id":        meta.get("chunk_id", -1),
            "start_time":      meta.get("start_time", 0.0),
            "end_time":        meta.get("end_time",   0.0),
            "fused_score":     round(float(fused_score), 6),
            "visual_score":    round(float(v_score), 6),
            "speech_score":    round(float(s_score), 6),
            "ocr_score":       round(float(o_score), 6),
            "modality_weights": weights,
        })

    # ── Sort by fused score descending ─────────────────────────────────────────
    fused.sort(key=lambda x: x["fused_score"], reverse=True)
    top_results = fused[:top_k]
    for i, r in enumerate(top_results):
        r["rank"] = i + 1

    return {
        "results":          top_results,
        "modality":         modality_info["modality"],
        "weights":          weights,
        "total_candidates": len(all_sids),
        "query":            query,
        "weighting_mode":   weighting_mode,
    }
