# Phase 1 — Tasks

## ML Service — New Services
- [x] `ml-service/app/services/__init__.py`
- [x] `ml-service/app/db.py`
- [x] `ml-service/app/services/clip_model.py`
- [x] `ml-service/app/services/segmentation.py`
- [x] `ml-service/app/services/whisper_asr.py`
- [x] `ml-service/app/services/ocr_service.py`
- [x] `ml-service/app/services/faiss_manager.py`
- [x] `ml-service/app/services/indexing_pipeline.py`

## ML Service — Updated Routes
- [x] `ml-service/app/routes/index_route.py` (real pipeline as BackgroundTask)

## Root
- [x] `ml-service/frames/` added to .gitignore
- [x] FAISS startup initialization in main.py lifespan

## Verification
- [x] All Phase 1 module imports: OK
- [ ] FastAPI server starts cleanly
- [ ] Upload test video → segments in MongoDB + FAISS files on disk
