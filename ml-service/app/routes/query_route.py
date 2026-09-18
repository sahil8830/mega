from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class QueryExpandRequest(BaseModel):
    query: str
    num_variants: int = 8  # LLM generates this many; K-Means reduces to 3 representatives


class QueryExpandResponse(BaseModel):
    original_query: str
    all_variants: list[str]
    representative_variants: list[str]  # K-Means cluster centroids (K=3)
    cached: bool


@router.post("/ml/query/expand", response_model=QueryExpandResponse, tags=["Query"])
async def expand_query(request: QueryExpandRequest):
    """
    GQE-style query expansion followed by K-Means clustering.

    Pipeline (Phase 2 implementation):
      1. Use flan-t5-base (local) or GPT-3.5 (API) to generate `num_variants` diverse query variants
      2. Encode all variants with CLIP text encoder
      3. Apply K-Means (K=3) clustering on variant embeddings
      4. Select one representative (closest to centroid) per cluster
      5. Cache result in MongoDB keyed by query hash

    Currently returns a stub response — full implementation in Phase 2.
    """
    # TODO (Phase 2): implement GQE expansion + K-Means clustering
    return QueryExpandResponse(
        original_query=request.query,
        all_variants=[],
        representative_variants=[],
        cached=False,
    )
