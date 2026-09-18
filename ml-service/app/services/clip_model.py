"""
CLIP Model Singleton — lazy-loads once, shared across all pipeline calls.

Uses open_clip to load ViT-B-32 (512-dim embeddings).
All embeddings are L2-normalized so cosine similarity == inner product (for FAISS IndexFlatIP).
"""
from functools import lru_cache
from typing import List

import numpy as np
import open_clip
import torch
from PIL import Image

from app.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_clip_model():
    """
    Load and cache the CLIP model, preprocessor, and tokenizer.
    Called once on first use; subsequent calls return the cached instance.
    """
    device = settings.device
    print(f"[CLIP] Loading {settings.clip_model_name} ({settings.clip_pretrained}) on {device}...")

    model, _, preprocess = open_clip.create_model_and_transforms(
        settings.clip_model_name,
        pretrained=settings.clip_pretrained,
    )
    tokenizer = open_clip.get_tokenizer(settings.clip_model_name)

    model = model.to(device)
    model.eval()

    print(f"[CLIP] Model loaded. Embedding dim: {model.visual.output_dim}")
    return model, preprocess, tokenizer


def encode_images(images: List[Image.Image]) -> np.ndarray:
    """
    Encode a list of PIL Images into CLIP visual embeddings.

    Returns:
        np.ndarray of shape (N, 512), L2-normalized.
    """
    model, preprocess, _ = get_clip_model()
    device = settings.device

    tensors = torch.stack([preprocess(img) for img in images]).to(device)

    with torch.no_grad():
        embeddings = model.encode_image(tensors)
        embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

    return embeddings.cpu().numpy().astype(np.float32)


def encode_texts(texts: List[str]) -> np.ndarray:
    """
    Encode a list of text strings into CLIP text embeddings.

    Returns:
        np.ndarray of shape (N, 512), L2-normalized.
        Zero vectors for empty strings.
    """
    model, _, tokenizer = get_clip_model()
    device = settings.device

    results = np.zeros((len(texts), model.visual.output_dim), dtype=np.float32)

    non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
    if not non_empty:
        return results

    indices, valid_texts = zip(*non_empty)
    tokens = tokenizer(list(valid_texts)).to(device)

    with torch.no_grad():
        embeddings = model.encode_text(tokens)
        embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

    for i, idx in enumerate(indices):
        results[idx] = embeddings[i].cpu().numpy()

    return results


def mean_pool(embeddings: np.ndarray) -> np.ndarray:
    """
    Mean-pool a set of embeddings and re-normalize.

    Args:
        embeddings: shape (N, D)
    Returns:
        shape (D,), L2-normalized
    """
    pooled = embeddings.mean(axis=0)
    norm = np.linalg.norm(pooled)
    if norm > 1e-8:
        pooled = pooled / norm
    return pooled.astype(np.float32)
