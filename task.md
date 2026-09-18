# Phase 2 — Query Expansion, Clustering & Multimodal Fusion (COMPLETE)

## ML Service — New Services
- [x] `ml-service/app/services/query_expander.py`  (GQE: flan-t5-base variants + K-Means clustering + MongoDB cache)
- [x] `ml-service/app/services/modality_classifier.py`  (rule-based keyword classifier with conjugated patterns)
- [x] `ml-service/app/services/retrieval.py`  (multi-query FAISS search + fixed-weight fusion)

## ML Service — Updated Routes
- [x] `ml-service/app/routes/query_route.py`  (POST /ml/query/expand)
- [x] `ml-service/app/routes/search_route.py`  (POST /ml/search)

## Backend — Updated
- [x] `backend/src/routes/search.js`  (GQE expand → ML search → persist Query + Results)
- [x] `backend/src/models/Query.js`  (expanded schema: modality, weights, resultCount)
- [x] `backend/src/models/Result.js`  (added fusedScore field)

## Verification
- [x] All Phase 2 module imports: OK
- [x] Modality classifier smoke test:
  - "show the red car on the whiteboard" → visual (60/20/20)
  - "find the code snippet for sorting algorithm" → ocr (100%)
  - "find where the professor explains gradient descent" → speech (fixed)
- [ ] End-to-end: query → expand → FAISS → fused results (needs indexed video)
