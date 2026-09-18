"""
GQE-Style Query Expander.

Uses google/flan-t5-base (local) to generate semantically diverse query variants
from a raw user query.  Results are cached in MongoDB (keyed by SHA-256 of the
query) to avoid redundant LLM calls.

Pipeline:
  1. Hash query → check MongoDB cache
  2. If cache miss → run flan-t5 to generate N variants
  3. Embed all variants with CLIP text encoder
  4. K-Means cluster (K=3) → pick centroid-closest representative per cluster
  5. Cache in MongoDB and return

Output:
  {
    "original": "...",
    "variants": ["...", ...],          # all N variants
    "representatives": ["...", ...],   # 3 cluster centroids (for FAISS)
    "representative_embeddings": [...] # shape (3, 512) — ready for search
  }
"""
import hashlib
import json
from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np
from sklearn.cluster import KMeans

from app.config import get_settings
from app.db import get_db
from app.services.clip_model import encode_texts

settings = get_settings()

# ─── Prompts ─────────────────────────────────────────────────────────────────
_EXPANSION_PROMPT = (
    "Generate {n} diverse search queries about the same topic as: '{query}'. "
    "Each query should approach the topic differently. "
    "Output only the queries, one per line, no numbering."
)

N_VARIANTS = 8      # how many variants to generate
N_CLUSTERS = 3      # how many representative queries to keep


# ─── Model Singleton ─────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_t5_pipeline():
    """Lazy-load flan-t5-base text2text pipeline."""
    from transformers import pipeline as hf_pipeline
    print("[GQE] Loading flan-t5-base...")
    pipe = hf_pipeline(
        "text2text-generation",
        model="google/flan-t5-base",
        device=-1,          # CPU
        max_new_tokens=256,
    )
    print("[GQE] flan-t5-base loaded.")
    return pipe


# ─── Core Functions ───────────────────────────────────────────────────────────
def _query_hash(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()


def _generate_variants_local(query: str) -> List[str]:
    """Generate query variants using flan-t5-base locally."""
    pipe = _get_t5_pipeline()
    prompt = _EXPANSION_PROMPT.format(n=N_VARIANTS, query=query)

    outputs = pipe(
        prompt,
        num_return_sequences=N_VARIANTS,
        do_sample=True,
        temperature=0.8,
        top_p=0.9,
    )

    variants = []
    for out in outputs:
        text = out["generated_text"].strip()
        # Split on newlines in case model returns multiple lines in one output
        for line in text.split("\n"):
            line = line.strip().lstrip("-•*0123456789.) ")
            if line and line.lower() != query.lower():
                variants.append(line)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)

    return unique[:N_VARIANTS] if unique else [query]


def _cluster_and_select(
    query: str,
    variants: List[str],
) -> Dict:
    """
    Embed all variants + original, K-Means cluster, pick one per cluster.

    Returns dict with:
      - representatives: List[str]
      - representative_embeddings: np.ndarray (K, 512)
      - all_embeddings: np.ndarray (N+1, 512)
    """
    all_texts = [query] + variants
    all_embs = encode_texts(all_texts)   # (N+1, 512)

    k = min(N_CLUSTERS, len(all_texts))
    if k == 1:
        return {
            "representatives": [query],
            "representative_embeddings": all_embs[:1],
            "all_embeddings": all_embs,
        }

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(all_embs)

    representatives = []
    rep_embs = []
    for cluster_id in range(k):
        cluster_mask = labels == cluster_id
        cluster_indices = np.where(cluster_mask)[0]
        if len(cluster_indices) == 0:
            continue
        centroid = km.cluster_centers_[cluster_id]
        dists = np.linalg.norm(all_embs[cluster_indices] - centroid, axis=1)
        closest = cluster_indices[np.argmin(dists)]
        representatives.append(all_texts[closest])
        rep_embs.append(all_embs[closest])

    return {
        "representatives": representatives,
        "representative_embeddings": np.stack(rep_embs),   # (K, 512)
        "all_embeddings": all_embs,
    }


async def expand_query(query: str) -> Dict:
    """
    Main entry point. Returns expansion result, using MongoDB cache if available.

    Return shape:
    {
        "original": str,
        "variants": List[str],
        "representatives": List[str],
        "representative_embeddings": List[List[float]],  # (K, 512)
        "from_cache": bool
    }
    """
    query = query.strip()
    q_hash = _query_hash(query)
    db = get_db()

    # ── Check cache ────────────────────────────────────────────────────────────
    cached = await db["query_cache"].find_one({"queryHash": q_hash})
    if cached:
        return {
            "original": query,
            "variants": cached["variants"],
            "representatives": cached["representatives"],
            "representative_embeddings": cached["representativeEmbeddings"],
            "from_cache": True,
        }

    # ── Generate variants ──────────────────────────────────────────────────────
    try:
        variants = _generate_variants_local(query)
    except Exception as e:
        print(f"[GQE] Variant generation failed: {e}. Falling back to original query only.")
        variants = []

    # ── Cluster + select representatives ──────────────────────────────────────
    cluster_result = _cluster_and_select(query, variants)
    representatives = cluster_result["representatives"]
    rep_embs = cluster_result["representative_embeddings"].tolist()

    # ── Cache in MongoDB ───────────────────────────────────────────────────────
    await db["query_cache"].update_one(
        {"queryHash": q_hash},
        {"$set": {
            "queryHash": q_hash,
            "originalQuery": query,
            "variants": variants,
            "representatives": representatives,
            "representativeEmbeddings": rep_embs,
        }},
        upsert=True,
    )

    return {
        "original": query,
        "variants": variants,
        "representatives": representatives,
        "representative_embeddings": rep_embs,
        "from_cache": False,
    }
