# Phase 1 — Offline Multimodal Indexing Pipeline

## Goal
Build the full offline indexing pipeline: **video → segments → CLIP embeddings + Whisper ASR + PaddleOCR → FAISS indices + MongoDB**.

After Phase 1, uploading a video automatically triggers a background job that:
1. Slices the video into overlapping 10s chunks
2. Samples 2 representative frames per chunk
3. Generates CLIP visual embeddings (mean-pooled across frames)
4. Transcribes audio with Whisper and maps to chunks
5. Extracts on-screen text with PaddleOCR
6. Encodes transcript + OCR text with CLIP text encoder
7. Stores all embeddings in 3 FAISS `IndexFlatIP` indices + MongoDB `segments`

> **Note:** Steps 1.1 (video upload) and 1.7 (BullMQ worker skeleton) were already built in Phase 0. This phase implements the Python ML pipeline they call.

---

## Proposed Changes

### `/ml-service` — New Services

#### [NEW] `ml-service/app/services/__init__.py`
Empty package init.

#### [NEW] `ml-service/app/services/segmentation.py`
**Temporal Segmentation** — `ffprobe` + `ffmpeg-python` + OpenCV
- `get_video_duration(path)` → float seconds
- `segment_video(path, chunk_size=10, overlap=2)` → `List[ChunkInfo]`
  - Each `ChunkInfo`: `{ chunk_id, start_time, end_time, frame_paths[] }`
- `sample_frames(video_path, start, end, n_frames=2)` → list of PIL Images (saved to temp dir)

#### [NEW] `ml-service/app/services/clip_model.py`
**CLIP Model Singleton** — lazy-loads once, reused across requests
- `get_clip_model()` → `(model, preprocess, tokenizer)` cached with `@lru_cache`
- `encode_images(images)` → `np.ndarray` shape `(N, 512)`, L2-normalized
- `encode_texts(texts)` → `np.ndarray` shape `(N, 512)`, L2-normalized
- `mean_pool_embeddings(embeddings)` → `np.ndarray` shape `(512,)`, L2-normalized

#### [NEW] `ml-service/app/services/whisper_asr.py`
**Whisper ASR** — transcribe audio + map segments to chunks
- `get_whisper_model()` → cached Whisper model
- `transcribe_video(video_path)` → `List[{ start, end, text }]` (word-level segments)
- `map_transcript_to_chunks(segments, chunks)` → `Dict[chunk_id, str]` (transcript per chunk)

#### [NEW] `ml-service/app/services/ocr_service.py`
**PaddleOCR** — extract on-screen text from frames
- `get_ocr_engine()` → cached PaddleOCR instance
- `extract_text_from_frame(image_path)` → `str`
- `extract_text_from_chunk(frame_paths)` → concatenated text string (empty string if none)

#### [NEW] `ml-service/app/services/faiss_manager.py`
**FAISS Index Manager** — manages 3 `IndexFlatIP` indices on disk
- `FaissManager` class with `visual`, `speech`, `ocr` indices
- `add(visual_emb, speech_emb, ocr_emb, metadata)` → `faiss_ids` dict
- `save()` — saves all 3 indices + an ID-to-metadata JSON map to `settings.faiss_index_path`
- `load()` — loads indices from disk on startup
- `search(query_emb, index_type, top_k)` → `List[{ faiss_id, score, metadata }]`

#### [NEW] `ml-service/app/services/indexing_pipeline.py`
**Pipeline Orchestrator** — wires all services together
- `async run_indexing_pipeline(video_id, video_filename)` → `IndexingResult`
  1. Segment video
  2. For each chunk: sample frames, encode visual (CLIP), transcribe (Whisper), OCR frames
  3. Encode text modalities with CLIP text encoder
  4. Add to FAISS indices
  5. Write `Segment` documents to MongoDB via `motor`
  6. Save FAISS indices to disk
  7. Return summary stats

#### [NEW] `ml-service/app/db.py`
Motor (async MongoDB) client singleton for the ML service.

---

### `/ml-service` — Updated Routes

#### [MODIFY] `ml-service/app/routes/index_route.py`
- Replace stub body with real call to `run_indexing_pipeline()`
- Run pipeline in a `BackgroundTask` so the HTTP call returns immediately with `{ status: "indexing" }`
- On completion, logs result; errors surface in BullMQ retry logic

---

### `/backend` — No changes needed
The BullMQ worker (`indexingQueue.js`) already calls `POST /ml/index` — it will now get real results.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| CLIP model | `ViT-B-32` (512-dim) | Balance of speed and accuracy for Phase 1 |
| Chunk size | 10s with 2s overlap | Standard in literature; adjustable via `.env` |
| Frames per chunk | 2 (first + middle) | Captures scene start and midpoint cheaply |
| Whisper model | `base` | Good accuracy, runs on CPU in reasonable time |
| FAISS index type | `IndexFlatIP` | Exact inner-product search; upgrade to HNSW in Phase 7 if needed |
| Text encoding | CLIP text encoder | Same embedding space as visual — enables cross-modal comparison |
| Pipeline mode | `BackgroundTasks` (FastAPI) | Non-blocking HTTP; BullMQ handles retries |

---

## Verification Plan

### Automated
```bash
# Start FastAPI
cd ml-service && venv\Scripts\uvicorn main:app --reload --port 8001

# Start backend
cd backend && npm run dev

# Upload a short test video (any .mp4)
curl -X POST http://localhost:3000/api/auth/login ...  # get token
curl -X POST http://localhost:3000/api/videos/upload -F "file=@test.mp4" -F "title=Test"

# Poll status
curl http://localhost:3000/api/videos/<id>/status

# Check MongoDB — segments collection should have documents
```

### Manual
- After indexing completes: MongoDB `segments` collection has N documents (one per chunk)
- FAISS directory has `faiss_visual.index`, `faiss_speech.index`, `faiss_ocr.index`
- Each segment has non-zero `visualEmbedding` array (length 512)
