"""
Dynamic Query-Conditioned Modality Weighting Module (Phase 3).

This is the CORE NOVEL CONTRIBUTION of the project.

Architecture:
  Input:  query_embedding (512-dim) concatenated with modality_scores (3-dim) = 515-dim
  Hidden: 256 -> 64 (ReLU, Dropout 0.3)
  Output: 3 weights [w_visual, w_speech, w_ocr] via Softmax (sum to 1.0)

The weights are PER-QUERY - conditioned on both the semantic content of the query
AND the actual retrieval scores from FAISS (so the module learns "given this query
AND these raw scores, which modality should be trusted more?").

Contrast with Phase 2 fixed weights (0.33 / 0.33 / 0.34) - those are static global
constants that cannot adapt to the specific query content.

Training signal (Step 3.2): soft labels derived from QVHighlights ground-truth moments.
If the correct moment is found only by visual search -> label = [1, 0, 0], etc.

Saved weights: ml-service/weights/weighting_module.pt
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

WEIGHTS_DIR = Path(__file__).parent.parent.parent / "weights"
WEIGHTS_DIR.mkdir(exist_ok=True)
WEIGHTS_PATH = str(WEIGHTS_DIR / "weighting_module.pt")

QUERY_DIM   = 512   # CLIP ViT-B/32 embedding dimension
SCORE_DIM   = 3     # [visual_score, speech_score, ocr_score]
INPUT_DIM   = QUERY_DIM + SCORE_DIM   # 515
HIDDEN1_DIM = 256
HIDDEN2_DIM = 64
OUTPUT_DIM  = 3     # [w_visual, w_speech, w_ocr]

# The QVHighlights checkpoint has no OCR-dominant training examples and learns
# a strong speech prior. Use deployment-encoder semantic intent to complement
# that score-conditioned model, rather than presenting its prior as query intent.
INTENT_PROMPTS = (
    ("show a person running, jumping or moving", "show what happens in the scene",
     "find a visible object, person or action", "show the player running across the field"),
    ("what does the speaker say", "a commentator explains and talks about the game",
     "find spoken words in the audio", "what does the commentator say about the goal"),
    ("read the text displayed on screen", "read the score on the scoreboard",
     "find written words, numbers or code on a slide", "read a caption or subtitle"),
)


@lru_cache(maxsize=1)
def _intent_embeddings() -> np.ndarray:
    from app.services.clip_model import encode_texts
    return encode_texts([prompt for group in INTENT_PROMPTS for prompt in group]).reshape(3, 4, QUERY_DIM)


def predict_fusion_weights(query_emb: np.ndarray, modality_scores: np.ndarray,
                           query: str = "") -> np.ndarray:
    """Hybrid weighting: query intent plus the trained score MLP.

    Prototypes use the same encoder as live queries. The original checkpoint is
    preserved; this is zero-shot intent calibration, not retrained modality labels.
    """
    learned = predict_weights(query_emb, modality_scores)
    similarities = np.einsum("mpd,d->mp", _intent_embeddings(), query_emb).max(axis=1)
    logits = similarities / 0.05
    intent = np.exp(logits - logits.max())
    intent /= intent.sum()
    if query:
        from app.services.modality_classifier import classify_modality
        info = classify_modality(query)
        if sum(info.get("debug_scores", {}).values()) > 0:
            # Explicit requests to read/speak/show complement ambiguous CLIP
            # semantics. This existing rule-based signal is not a trained label.
            explicit = np.array([info["weights"][name] for name in ("visual", "speech", "ocr")])
            intent = 0.5 * intent + 0.5 * explicit
    return (0.75 * intent + 0.25 * learned).astype(np.float32)


class ModalityWeightingMLP(nn.Module):
    """
    Small MLP that predicts per-query modality fusion weights.

    Input shape:  (batch, 515)  - [query_emb || visual_score, speech_score, ocr_score]
    Output shape: (batch, 3)    - softmax weights [w_visual, w_speech, w_ocr]
    """

    def __init__(self, dropout: float = 0.3):
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(INPUT_DIM, HIDDEN1_DIM),
            nn.LayerNorm(HIDDEN1_DIM),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(HIDDEN1_DIM, HIDDEN2_DIM),
            nn.LayerNorm(HIDDEN2_DIM),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(HIDDEN2_DIM, OUTPUT_DIM),
        )

    def forward(self, query_emb: torch.Tensor, modality_scores: torch.Tensor) -> torch.Tensor:
        """
        Args:
            query_emb:       (batch, 512) - L2-normalized CLIP query embedding
            modality_scores: (batch, 3)   - [visual_sim, speech_sim, ocr_sim] from FAISS

        Returns:
            weights: (batch, 3) - softmax weights summing to 1.0
        """
        x = torch.cat([query_emb, modality_scores], dim=-1)   # (batch, 515)
        logits = self.net(x)                                   # (batch, 3)
        return F.softmax(logits, dim=-1)                       # (batch, 3)


# ─── Model Singleton ──────────────────────────────────────────────────────────
_weighting_model: Optional[ModalityWeightingMLP] = None


def get_weighting_model(device: str = "cpu") -> ModalityWeightingMLP:
    """
    Return the cached weighting module, loading weights from disk if available.
    Raises if no trained checkpoint exists so retrieval can use fixed weights.
    """
    global _weighting_model
    if _weighting_model is not None:
        return _weighting_model

    model = ModalityWeightingMLP()
    model = model.to(device)

    if os.path.exists(WEIGHTS_PATH):
        state = torch.load(WEIGHTS_PATH, map_location=device, weights_only=True)
        model.load_state_dict(state)
        print(f"[WeightingMLP] Loaded weights from {WEIGHTS_PATH}")
    else:
        raise FileNotFoundError(f"Trained weighting checkpoint missing: {WEIGHTS_PATH}")

    model.eval()
    _weighting_model = model
    return model


def weighting_status() -> dict:
    return {
        "loaded": _weighting_model is not None,
        "checkpoint_exists": os.path.isfile(WEIGHTS_PATH),
        "checkpoint_path": WEIGHTS_PATH,
        "fusion_method": "query_intent_and_mlp_v3",
    }


def predict_weights(
    query_emb: np.ndarray,         # (512,) - L2-normalized
    modality_scores: np.ndarray,   # (3,)   - [visual_sim, speech_sim, ocr_sim]
    device: str = "cpu",
) -> np.ndarray:
    """
    Predict dynamic fusion weights for a single query.

    Args:
        query_emb:       (512,) numpy array, L2-normalized CLIP embedding
        modality_scores: (3,) numpy array, raw FAISS similarity scores

    Returns:
        weights: (3,) numpy array - [w_visual, w_speech, w_ocr], sums to 1.0
    """
    model = get_weighting_model(device)

    q_t = torch.tensor(query_emb, dtype=torch.float32, device=device).unsqueeze(0)  # (1, 512)
    s_t = torch.tensor(modality_scores, dtype=torch.float32, device=device).unsqueeze(0)  # (1, 3)

    with torch.no_grad():
        w = model(q_t, s_t)  # (1, 3)

    return w.squeeze(0).cpu().numpy()


def save_model(model: ModalityWeightingMLP) -> None:
    """Save model state dict to disk."""
    torch.save(model.state_dict(), WEIGHTS_PATH)
    print(f"[WeightingMLP] Saved to {WEIGHTS_PATH}")
