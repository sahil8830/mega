# Phase 3 — Dynamic Query-Conditioned Modality Weighting (COMPLETE)

## Step 3.1 — MLP Architecture
- [x] `ml-service/app/services/weighting_module.py`
      - ModalityWeightingMLP: 515 → 256 → 64 → 3 (softmax)
      - 149,379 parameters
      - Input: query_emb(512) + modality_scores(3) = 515-dim
      - Output: [w_visual, w_speech, w_ocr] summing to 1.0
      - get_weighting_model() singleton, loads from weights/weighting_module.pt
      - predict_weights() numpy interface

## Step 3.2 — Training Script
- [x] `ml-service/train_weighting_module.py`
      - Synthetic 10k samples warm-start (Dirichlet scores + temperature soft labels)
      - Real data path: loads from MongoDB segments if available
      - Loss: KL divergence + CrossEntropy (0.5 each)
      - Optimizer: AdamW + CosineAnnealingLR
      - TensorBoard logging → ml-service/runs/weighting_mlp/
      - Saves best checkpoint to ml-service/weights/weighting_module.pt

## Step 3.3 — Integration
- [x] `ml-service/app/services/retrieval.py`
      - use_dynamic_weights=True → MLP predicts per-query weights
      - use_dynamic_weights=False → fixed modality-classifier weights (Phase 2)
      - Graceful fallback: MLP failure → equal weights
      - Returns weighting_mode: "dynamic" | "fixed"
- [x] `ml-service/app/routes/search_route.py`
      - Exposes use_dynamic_weights param
      - Returns weighting_mode in response

## Step 3.4 — Ablation
- [x] `ml-service/ablation.py`
      - Metrics: R@1, R@5, mIoU, MRR
      - Generates synthetic test pairs from MongoDB if no test file
      - Compares both modes side-by-side in formatted table
      - Saves JSON results to ablation_results.json

## Verification
- [x] MLP forward pass: (4, 515) → (4, 3), sum=1.0 OK
- [x] predict_weights numpy interface: weights sum to 1.0 OK
- [x] retrieve() dynamic mode: weighting_mode="dynamic" OK
- [x] retrieve() fixed mode: weighting_mode="fixed" OK
- [ ] Training: run `python train_weighting_module.py` (needs indexed videos for full training)
- [ ] Ablation: run `python ablation.py` (needs indexed videos for real metrics)
