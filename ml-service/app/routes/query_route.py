"""
POST /ml/query/expand — GQE-style query expansion.

Takes a raw user query and returns:
  - N semantically diverse variants (flan-t5-base)
  - 3 cluster-representative queries (K-Means on CLIP embeddings)
  - Pre-computed CLIP embeddings for the 3 representatives

The representatives + their embeddings are passed directly to POST /ml/search
to avoid re-encoding them.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

router = APIRouter()


class QueryExpandRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512, description="Raw user query")


class QueryExpandResponse(BaseModel):
    original: str
    variants: List[str]
    representatives: List[str]
    representative_embeddings: List[List[float]]   # shape (K, 512)
    from_cache: bool
    modality: str
    weights: dict


@router.post("/ml/query/expand", response_model=QueryExpandResponse, tags=["Query"])
async def expand_query_endpoint(request: QueryExpandRequest):
    """
    Expand a raw query into semantically diverse variants using flan-t5-base,
    then cluster to 3 representative queries and classify modality.

    - Variants: 8 paraphrases from the LLM
    - Representatives: 3 K-Means cluster centroids for efficient FAISS search
    - Modality: predicted dominant modality (visual / speech / ocr / all)
    - from_cache: true if result was served from MongoDB cache

    **First call** may take 30-60 seconds (model download + inference).
    **Subsequent calls** with the same query are instant (MongoDB cache hit).
    """
    from app.services.query_expander import expand_query
    from app.services.modality_classifier import classify_modality

    result = await expand_query(request.query)
    modality_info = classify_modality(request.query)

    return QueryExpandResponse(
        original=result["original"],
        variants=result["variants"],
        representatives=result["representatives"],
        representative_embeddings=result["representative_embeddings"],
        from_cache=result["from_cache"],
        modality=modality_info["modality"],
        weights=modality_info["weights"],
    )
