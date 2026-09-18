from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class Evidence(BaseModel):
    visual_weight: float
    speech_weight: float
    ocr_weight: float
    visual_similarity: float
    speech_similarity: float
    ocr_similarity: float


class SearchResult(BaseModel):
    video_id: str
    video_title: str
    start_time: float
    end_time: float
    answerability_score: float
    localization_confidence: float
    refinement_triggered: bool
    evidence: Evidence


class SearchResponse(BaseModel):
    status: str  # "ok" | "no_match"
    message: Optional[str] = None
    results: list[SearchResult] = []


@router.post("/ml/search", response_model=SearchResponse, tags=["Search"])
async def search(request: SearchRequest):
    """
    Run the full online query pipeline for a natural language query.

    Pipeline (Phase 2–5 implementation):
      1. GQE-style query expansion (Phase 2)
      2. K-Means clustering of variants (Phase 2)
      3. FAISS retrieval across 3 modality indices (Phase 2)
      4. Answerability detection (Phase 4)
      5. Dynamic modality weighting (Phase 3)
      6. Multimodal fusion & ranking (Phase 2–3)
      7. Temporal localization (Phase 5)
      8. Confidence-gated refinement (Phase 5)

    Currently returns a stub response — full implementation in Phases 2–5.
    """
    # TODO (Phase 2–5): implement full search pipeline
    return SearchResponse(
        status="stub",
        message="Search pipeline not yet implemented — Phase 2–5 work.",
        results=[],
    )
