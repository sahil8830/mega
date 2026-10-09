"""
POST /ml/search — End-to-end multimodal video search.

Accepts a raw query (optionally with pre-computed representative embeddings
from /ml/query/expand) and returns ranked segment results.

Full pipeline:
  1. If no embeddings provided → call expand_query() for GQE + embedding
  2. classify_modality() → compute fusion weights
  3. retrieve() → FAISS search + fixed/dynamic-weight fusion + re-rank
  4. compute_answerability() → gate results by confidence (Phase 4)
  5. Return top-K results with per-segment scores + answerability signal
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

router = APIRouter()

# ── Minimum output window ─────────────────────────────────────────────────────
# Chunks are kept small for fine-grained FAISS indexing (7s / 3s overlap).
# At query time every result is symmetrically padded so the user always sees
# at least MIN_RESULT_DURATION seconds of video context.
MIN_RESULT_DURATION = 15.0  # seconds

# NMS: suppress results whose overlap with a higher-ranked result exceeds this
NMS_IOU_THRESHOLD = 0.3   # 30% overlap → suppress


def _expand_window(start: float, end: float, video_duration: float = None) -> tuple:
    """
    Expand [start, end] to be at least MIN_RESULT_DURATION seconds wide.
    The window is grown symmetrically around the midpoint.
    If video_duration is known, the window is clamped so it never exceeds it.
    """
    duration = end - start
    if duration >= MIN_RESULT_DURATION:
        return start, end  # already long enough

    pad = (MIN_RESULT_DURATION - duration) / 2.0
    new_start = max(0.0, start - pad)
    new_end   = new_start + MIN_RESULT_DURATION

    if video_duration is not None and new_end > video_duration:
        new_end   = video_duration
        new_start = max(0.0, new_end - MIN_RESULT_DURATION)

    return round(new_start, 2), round(new_end, 2)


def _temporal_nms(results: list, iou_threshold: float = NMS_IOU_THRESHOLD) -> list:
    """
    Temporal Non-Maximum Suppression.

    Suppresses results that overlap significantly (IoU > threshold) with a
    higher-ranked result FROM THE SAME VIDEO.

    Results from different videos are never suppressed against each other —
    a user wants to see the best moment from EACH relevant video.

    Args:
        results:       List of result dicts, already sorted by fused_score desc.
        iou_threshold: Overlap ratio above which a lower-ranked result is suppressed.

    Returns:
        Filtered list with overlapping duplicates removed, ranks re-assigned.
    """
    kept = []   # (video_id, start, end, result_dict)

    for r in results:
        vid   = r.get("video_id", "")
        start = r.get("start_time", 0.0)
        end   = r.get("end_time",   0.0)

        # Check against all already-kept results from the SAME video
        suppressed = False
        for k_vid, k_start, k_end, _ in kept:
            if k_vid != vid:
                continue  # different video — always keep

            # Compute IoU (Intersection over Union) for temporal windows
            inter = max(0.0, min(end, k_end) - max(start, k_start))
            if inter == 0.0:
                continue

            union = max(end, k_end) - min(start, k_start)
            iou   = inter / union if union > 0 else 0.0

            if iou > iou_threshold:
                suppressed = True
                break

        if not suppressed:
            kept.append((vid, start, end, r))

    # Re-assign ranks
    final = []
    for rank, (_, _, _, r) in enumerate(kept, start=1):
        r = dict(r)
        r["rank"] = rank
        final.append(r)

    return final



class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    user_id: str = Field("global", description="User's MongoDB _id — scopes search to their FAISS index.")
    representative_embeddings: Optional[List[List[float]]] = Field(
        None,
        description="Pre-computed embeddings from /ml/query/expand. "
                    "If omitted, the query is encoded directly (no GQE).",
    )
    modality_weights: Optional[Dict[str, float]] = Field(
        None,
        description="Override fusion weights {visual, speech, ocr}. "
                    "Ignored when use_dynamic_weights=True.",
    )
    top_k: int = Field(10, ge=1, le=50, description="Number of results to return")
    use_dynamic_weights: bool = Field(
        False,
        description="Use the trained MLP weighting module (Phase 3 dynamic weights). "
                    "Falls back to fixed weights if model is untrained.",
    )
    answerability_check: bool = Field(
        True,
        description="Phase 4: Gate results by confidence score. "
                    "If the query cannot be answered by indexed videos, "
                    "returns answerable=false with empty results.",
    )
    min_confidence: float = Field(
        0.0,
        ge=0.0, le=1.0,
        description="Minimum confidence threshold (0=return all, 1=only perfect matches).",
    )
    refine_timestamps: bool = Field(
        True,
        description="Phase 5: Refine coarse timestamps to precise peak moments. "
                    "Runs Gaussian-smoothed sliding-window localization on top results.",
    )
    refine_top_k: int = Field(
        3, ge=1, le=10,
        description="How many top results to refine (default: 3).",
    )


class SegmentResult(BaseModel):
    rank: int
    segment_id: str
    video_id: str
    chunk_id: int
    start_time: float
    end_time: float
    fused_score: float
    visual_score: float
    speech_score: float
    ocr_score: float
    modality_weights: Dict[str, float]
    confidence: Optional[float] = None
    # Phase 5 refinement fields
    refined: Optional[bool] = None
    refined_score: Optional[float] = None
    coarse_start: Optional[float] = None
    coarse_end: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SegmentResult]
    modality: str
    weights: Dict[str, float]
    total_candidates: int
    gqe_applied: bool
    weighting_mode: str           # "fixed" | "dynamic"
    # Phase 4 answerability fields
    answerable: bool = True
    confidence: float = 1.0
    answerability_reason: str = "not_checked"


@router.post("/ml/search", response_model=SearchResponse, tags=["Search"])
async def search_endpoint(request: SearchRequest):
    """
    Multimodal video moment retrieval with answerability detection.

    **Without pre-computed embeddings** (simple mode):
    - Encodes the raw query with CLIP directly
    - No GQE expansion — faster but lower recall

    **With pre-computed embeddings** (full GQE mode):
    - Pass `representative_embeddings` from `POST /ml/query/expand`
    - Uses 3 cluster-representative queries for better recall

    **Answerability detection** (Phase 4):
    - If `answerability_check=true`, validates that results are genuinely relevant
    - Returns `answerable: false` with empty results when no good match exists
    - Use `min_confidence` to control strictness (0.0 = lenient, 1.0 = strict)

    Returns ranked segments with per-modality scores, fusion weights,
    and an answerability signal.
    """
    import numpy as np
    from app.services.retrieval import retrieve
    from app.services.answerability import compute_answerability, filter_by_answerability

    rep_embs = None
    gqe_applied = False

    if request.representative_embeddings:
        rep_embs = np.array(request.representative_embeddings, dtype=np.float32)
        gqe_applied = True

    result = retrieve(
        query=request.query,
        representative_embeddings=rep_embs,
        modality_weights=request.modality_weights,
        top_k=request.top_k,
        use_dynamic_weights=request.use_dynamic_weights,
        user_id=request.user_id,
    )

    raw_results = result["results"]

    # ── Phase 4: Answerability Detection ─────────────────────────────────────
    answerable      = True
    confidence      = 1.0
    answer_reason   = "not_checked"

    if request.answerability_check:
        # Extract per-modality scores for top results
        visual_scores = [r.get("visual_score", 0.0) for r in raw_results]
        speech_scores = [r.get("speech_score", 0.0) for r in raw_results]
        ocr_scores    = [r.get("ocr_score",    0.0) for r in raw_results]

        # Map fused_score → score for answerability (retrieval uses fused_score key)
        for r in raw_results:
            if "score" not in r:
                r["score"] = r.get("fused_score", 0.0)

        answerability = compute_answerability(
            results=raw_results,
            visual_scores=visual_scores,
            speech_scores=speech_scores,
            ocr_scores=ocr_scores,
        )

        answerable    = answerability["answerable"]
        confidence    = answerability["confidence"]
        answer_reason = answerability["reason"]

        # Apply min_confidence override
        if confidence < request.min_confidence:
            answerable    = False
            answer_reason = "below_min_confidence"

        # Filter results: empty if not answerable
        raw_results = filter_by_answerability(raw_results, answerability)

    # ── Phase 5: Temporal Localization Refinement ─────────────────────────────
    if raw_results and request.refine_timestamps and answerable:
        try:
            from app.services.localizer import refine_results
            from app.services.faiss_manager import get_faiss_manager
            from app.services.clip_model import encode_texts

            # Reuse pre-computed embeddings if available (skip redundant CLIP call)
            if rep_embs is not None:
                q_emb = rep_embs.mean(axis=0)          # mean of rep embeddings (512,)
            else:
                q_emb = encode_texts([request.query])[0]  # (512,) — only if no GQE
            q_emb = q_emb / (np.linalg.norm(q_emb) + 1e-8)

            faiss_mgr = get_faiss_manager(request.user_id)
            raw_results = refine_results(
                query_emb=q_emb,
                results=raw_results,
                faiss_manager=faiss_mgr,
                refine_top_k=request.refine_top_k,
                min_confidence=0.3,
            )
        except Exception as e:
            # Refinement is best-effort — don't fail the whole search
            print(f"[Phase5] Refinement skipped: {e}")


    # ── Expand every result window to MIN_RESULT_DURATION ────────────────────
    # Done AFTER refinement so we never shrink a correctly-refined window.
    for r in raw_results:
        r["start_time"], r["end_time"] = _expand_window(
            r.get("start_time", 0.0),
            r.get("end_time",   0.0),
        )
        # Sync coarse timestamps if they exist
        if r.get("coarse_start") is not None:
            r["coarse_start"], r["coarse_end"] = _expand_window(
                r["coarse_start"], r["coarse_end"]
            )

    # ── Temporal NMS — remove overlapping windows from the same video ─────────
    # Must run AFTER expansion so IoU is computed on the final 15s windows.
    # Results from different videos are never suppressed against each other.
    raw_results = _temporal_nms(raw_results)

    return SearchResponse(
        query=result["query"],
        results=[SegmentResult(**r) for r in raw_results],
        modality=result["modality"],
        weights=result["weights"],
        total_candidates=result["total_candidates"],
        gqe_applied=gqe_applied,
        weighting_mode=result.get("weighting_mode", "fixed"),
        answerable=answerable,
        confidence=confidence,
        answerability_reason=answer_reason,
    )
