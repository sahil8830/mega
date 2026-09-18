# Phase 2 — Query Expansion, Clustering & Multimodal Fusion

## ML Service — New Services
- [ ] `ml-service/app/services/query_expander.py`  (GQE: flan-t5-base variants + MongoDB cache)
- [ ] `ml-service/app/services/modality_classifier.py`  (rule-based keyword classifier)
- [ ] `ml-service/app/services/retrieval.py`  (FAISS search + fixed-weight fusion)

## ML Service — Updated Routes
- [ ] `ml-service/app/routes/query_route.py`  (POST /ml/query/expand — real implementation)
- [ ] `ml-service/app/routes/search_route.py`  (POST /ml/search — end-to-end retrieval)

## Backend — Updated Routes
- [ ] `backend/src/routes/search.js`  (proxy /api/search → ML service, store Query + Results in MongoDB)

## Verification
- [ ] POST /ml/query/expand returns variants + cluster representatives
- [ ] POST /ml/search returns ranked results with scores
- [ ] End-to-end: query → expand → FAISS → fused results
