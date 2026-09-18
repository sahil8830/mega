"""
POST /ml/search — End-to-end multimodal video search.

Accepts a raw query (optionally with pre-computed representative embeddings
from /ml/query/expand) and returns ranked segment results.

Full pipeline:
  1. If no embeddings provided → call expand_query() for GQE + embedding
  2. classify_modality() → compute fusion weights
  3. retrieve() → FAISS search + fixed-weight fusion + re-rank
  4. Return top-K results with per-segment scores
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    representative_embeddings: Optional[List[List[float]]] = Field(
        None,
        description="Pre-computed embeddings from /ml/query/expand. "
                    "If omitted, the query is encoded directly (no GQE).",
    )
    modality_weights: Optional[Dict[str, float]] = Field(
        None,
        description="Override fusion weights {visual, speech, ocr}. "
                    "If omitted, weights are inferred from modality classifier.",
    )
    top_k: int = Field(10, ge=1, le=50, description="Number of results to return")


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


class SearchResponse(BaseModel):
    query: str
    results: List[SegmentResult]
    modality: str
    weights: Dict[str, float]
    total_candidates: int
    gqe_applied: bool


@router.post("/ml/search", response_model=SearchResponse, tags=["Search"])
async def search_endpoint(request: SearchRequest):
    """
    Multimodal video moment retrieval.

    **Without pre-computed embeddings** (simple mode):
    - Encodes the raw query with CLIP directly
    - No GQE expansion — faster but lower recall

    **With pre-computed embeddings** (full GQE mode):
    - Pass `representative_embeddings` from `POST /ml/query/expand`
    - Uses 3 cluster-representative queries for better recall

    Returns ranked segments with per-modality scores and fusion weights.
    """
    import numpy as np
    from app.services.retrieval import retrieve

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
    )

    return SearchResponse(
        query=result["query"],
        results=[SegmentResult(**r) for r in result["results"]],
        modality=result["modality"],
        weights=result["weights"],
        total_candidates=result["total_candidates"],
        gqe_applied=gqe_applied,
    )
