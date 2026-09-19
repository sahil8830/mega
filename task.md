# Phase 3 — Dynamic Query-Conditioned Modality Weighting

## Step 3.1 — MLP Weighting Module
- [ ] `ml-service/app/services/weighting_module.py`  (MLP architecture: 512+3 → 64 → 3, softmax output)

## Step 3.2 — Training Pipeline
- [ ] `ml-service/train_weighting_module.py`  (training script: synthetic labels + triplet loss + TensorBoard)

## Step 3.3 — Integration
- [ ] `ml-service/app/services/retrieval.py`  (add `use_dynamic_weights` flag, swap fixed→MLP weights)
- [ ] `ml-service/app/routes/search_route.py`  (expose `use_dynamic_weights` param + per-modality weight in response)

## Step 3.4 — Ablation
- [ ] `ml-service/ablation.py`  (evaluate fixed-weight vs dynamic-weight on a test set; print R@1, R@5, mIoU)

## Verification
- [ ] Module loads and produces valid softmax weights from a 512-dim query embedding
- [ ] Training script runs without error (even on synthetic data)
- [ ] POST /ml/search with dynamic_weights=true returns MLP-derived weights
