"""
Multimodal Retrieval Service.

Handles FAISS search across all three modalities (visual, speech, OCR)
and fuses their scores into a single ranked result list.

Two fusion modes:
  - Fixed-Weight (Phase 2 baseline): weights from modality classifier or user override
  - Dynamic-Weight: query intent calibrated with the trained score-conditioned MLP

Dynamic weighting is the CORE NOVEL CONTRIBUTION:
  query_emb -> MLP(query_emb || top_scores) -> [w_visual, w_speech, w_ocr]
  fused_score = w_v * visual_sim + w_s * speech_sim + w_o * ocr_sim
"""
from typing import Dict, List, Optional
import concurrent.futures

import numpy as np

from app.services.clip_model import encode_texts
from app.services.faiss_manager import get_faiss_manager
from app.services.modality_classifier import classify_modality
from app.services.text_matching import text_coverage

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


def _multi_query_search_with(
    faiss_mgr,
    rep_embeddings: np.ndarray,   # (K, 512)
    index_type: str,
    top_k: int,
) -> List[Dict]:
    """
    Search a specific FaissManager instance with multiple embeddings.
    Used when searching a user's private index.
    """
    best: Dict[str, Dict] = {}

    for emb in rep_embeddings:
        results = faiss_mgr.search(emb, index_type=index_type, top_k=top_k)
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
    query: str = "",
) -> Dict[str, float]:
    """
    Compute hybrid per-query fusion weights from intent and the trained MLP.
    Errors propagate to retrieve(), which reports a fixed-weight fallback.
    """
    from app.services.weighting_module import predict_fusion_weights
    modality_scores = np.array([v_score, s_score, o_score], dtype=np.float32)
    w = predict_fusion_weights(query_emb, modality_scores, query=query)
    if not np.isfinite(w).all() or np.any(w < 0) or not np.isclose(w.sum(), 1.0):
        raise ValueError("Weighting model returned invalid weights")
    return {"visual": float(w[0]), "speech": float(w[1]), "ocr": float(w[2])}


def retrieve(
    query: str,
    representative_embeddings: Optional[np.ndarray] = None,
    modality_weights: Optional[Dict[str, float]] = None,
    top_k: int = FINAL_TOP_K,
    use_dynamic_weights: bool = False,
    user_id: str = "global",
    allowed_video_ids: Optional[set] = None,
    text_candidates: Optional[List[Dict]] = None,
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
    # ── Modality classification ───────────────────────────────────────────────
    # When dynamic weights are active the MLP overrides classifier weights,
    # so we still call it (fast) just to get the modality LABEL for the UI.
    modality_info = classify_modality(query)

    # Always include the original query. Expansions only propose candidates;
    # final scoring uses the original intent without a sports-specific prompt.
    raw_query_emb = encode_texts([query])[0]
    raw_query_emb = raw_query_emb / max(float(np.linalg.norm(raw_query_emb)), 1e-8)
    rep_embs = raw_query_emb[None, :]
    if representative_embeddings is not None:
        extra = np.asarray(representative_embeddings, dtype=np.float32)
        rep_embs = np.vstack([rep_embs, extra])

    # ── Get the user's FAISS manager ──────────────────────────────────────────
    faiss_mgr = get_faiss_manager(user_id)

    # ── Search all 3 indices IN PARALLEL (3× faster for large indexes) ────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        f_visual = pool.submit(_multi_query_search_with, faiss_mgr, rep_embs, "visual", TOP_K_PER_INDEX)
        f_speech = pool.submit(_multi_query_search_with, faiss_mgr, rep_embs, "speech", TOP_K_PER_INDEX)
        f_ocr    = pool.submit(_multi_query_search_with, faiss_mgr, rep_embs, "ocr",    TOP_K_PER_INDEX)
        visual_results = f_visual.result()
        speech_results = f_speech.result()
        ocr_results    = f_ocr.result()

    # ── Collect all segment_ids seen across modalities ────────────────────────
    all_sids = set(
        r.get("segment_id", str(r.get("faiss_id")))
        for results in [visual_results, speech_results, ocr_results]
        for r in results
    )
    texts = {str(doc["_id"]): doc for doc in (text_candidates or [])}
    all_sids.update(texts)

    # Rescore ALL candidates in ALL modalities against the original query.
    # No min-max scaling: a weak top match must not become a perfect 1.0.
    def rescore(modality):
        return [r for r in faiss_mgr.score_segments(raw_query_emb, all_sids, modality)
                if allowed_video_ids is None or r.get("video_id") in allowed_video_ids]

    visual_results = rescore("visual")
    speech_results = rescore("speech")
    ocr_results = rescore("ocr")
    all_sids = {r["segment_id"] for rows in (visual_results, speech_results, ocr_results) for r in rows}

    # ── Build score maps per modality ─────────────────────────────────────────
    def _score_map(results: List[Dict]) -> Dict[str, float]:
        return {
            r.get("segment_id", str(r.get("faiss_id"))): max(0.0, min(1.0, r["score"]))
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
        # Match the L2-normalized query embeddings used during training.
        query_emb_for_mlp = np.array(raw_query_emb, dtype=np.float32)
        query_norm = np.linalg.norm(query_emb_for_mlp)
        if query_norm > 1e-8:
            query_emb_for_mlp = query_emb_for_mlp / query_norm

        # The MLP was trained on raw similarities. Min-max normalized top
        # scores are almost always 1, erasing query-specific evidence.
        top_v = max((r["score"] for r in visual_results), default=0.0)
        top_s = max((r["score"] for r in speech_results), default=0.0)
        top_o = max((r["score"] for r in ocr_results), default=0.0)

        try:
            weights = _get_dynamic_weights(query_emb_for_mlp, top_v, top_s, top_o, query=query)
            weighting_mode = "dynamic"
        except Exception as exc:
            print(f"[Retrieval] Dynamic weighting failed: {exc}. Using fixed weights.")
            weights = modality_weights if modality_weights is not None else modality_info["weights"]
    elif modality_weights is not None:
        weights = modality_weights
    else:
        weights = modality_info["weights"]

    # ── Dynamic weight zeroing for empty modalities (B3) ──────────────────────────
    # If a modality returned zero results, zero its weight and redistribute
    has_visual = len(visual_results) > 0
    has_speech = len(speech_results) > 0
    has_ocr    = len(ocr_results)    > 0

    if not (has_visual and has_speech and has_ocr):
        # At least one modality is empty — redistribute weights
        active_count = sum([has_visual, has_speech, has_ocr])
        if active_count == 0:
            weights = DEFAULT_WEIGHTS.copy()
        else:
            active = {"visual": has_visual, "speech": has_speech, "ocr": has_ocr}
            active_total = sum(weights.get(k, 0.0) for k, present in active.items() if present)
            # Preserve learned/override proportions, removing only unavailable
            # evidence. Equal weights are needed only when active mass is zero.
            weights = {
                k: (weights.get(k, 0.0) / active_total if active_total > 1e-8
                    else 1.0 / active_count) if present else 0.0
                for k, present in active.items()
            }
    # else: keep weights as determined by classifier/dynamic/override

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

        # Exact topic evidence complements CLIP's broad text similarity.
        # Blend only when the query has literal matches in the scoped corpus.
        # A pure visual request retains its visual contribution unchanged.
        if texts:
            doc = texts.get(sid, {})
            speech_match = text_coverage(query, doc.get("transcript", ""))
            ocr_match = text_coverage(query, doc.get("ocrText", ""))
            fused_score = (w_v * v_score
                           + w_s * (0.5 * s_score + 0.5 * speech_match)
                           + w_o * (0.5 * o_score + 0.5 * ocr_match))

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
        "weighting_method": "query_intent_and_mlp_v3" if weighting_mode == "dynamic" else "fixed",
    }
