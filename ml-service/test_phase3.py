"""Phase 3 smoke test — verifies MLP module works correctly."""
import numpy as np
import torch

from app.services.weighting_module import (
    ModalityWeightingMLP, get_weighting_model, predict_weights, WEIGHTS_PATH
)
from app.services.retrieval import retrieve

print("=== Phase 3 Smoke Test ===\n")

# 1. Test MLP architecture
model = ModalityWeightingMLP()
total_params = sum(p.numel() for p in model.parameters())
print(f"[1] MLP architecture: {total_params:,} parameters")

# Forward pass with random input
q_emb = torch.randn(4, 512)
scores = torch.softmax(torch.randn(4, 3), dim=-1)
weights = model(q_emb, scores)
assert weights.shape == (4, 3), f"Expected (4,3), got {weights.shape}"
assert abs(weights.sum(dim=-1).mean().item() - 1.0) < 1e-5, "Weights must sum to 1"
print(f"   Forward pass OK: output shape={tuple(weights.shape)}, sum~1.0 OK")

# 2. Test predict_weights with numpy
print(f"\n[2] predict_weights() — numpy interface:")
q_np = np.random.randn(512).astype(np.float32)
q_np /= np.linalg.norm(q_np)
scores_np = np.array([0.6, 0.3, 0.1], dtype=np.float32)  # visual-dominant
w = predict_weights(q_np, scores_np)
assert len(w) == 3, "Should return 3 weights"
assert abs(w.sum() - 1.0) < 1e-5, f"Weights must sum to 1, got {w.sum()}"
print(f"   Input scores: visual=0.6 speech=0.3 ocr=0.1")
print(f"   MLP weights: visual={w[0]:.4f} speech={w[1]:.4f} ocr={w[2]:.4f}")
print(f"   Sum={w.sum():.6f} OK")

# 3. Test retrieve() with use_dynamic_weights=True
print(f"\n[3] retrieve() with use_dynamic_weights=True (empty FAISS — should return no results):")
result = retrieve(
    query="find where the professor explains gradient descent",
    use_dynamic_weights=True,
)
print(f"   Weighting mode: {result['weighting_mode']}")
print(f"   Weights: {result['weights']}")
print(f"   Results: {len(result['results'])} (0 expected — no indexed videos)")
assert result["weighting_mode"] == "dynamic", "Expected dynamic mode"

# 4. Test retrieve() with use_dynamic_weights=False (Phase 2 baseline)
print(f"\n[4] retrieve() with use_dynamic_weights=False (fixed baseline):")
result2 = retrieve(
    query="show the red car on screen",
    use_dynamic_weights=False,
)
print(f"   Weighting mode: {result2['weighting_mode']}")
print(f"   Modality: {result2['modality']}")
print(f"   Weights: {result2['weights']}")
assert result2["weighting_mode"] == "fixed", "Expected fixed mode"

print(f"\n=== All Phase 3 checks passed! ===")
print(f"Next: run `python train_weighting_module.py` to train the MLP")
print(f"Then: run `python ablation.py` to compare fixed vs dynamic")
