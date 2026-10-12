# 🎯 Universal Semantic Video Search & Moment Retrieval

> **B.Tech CSE Final Year Project** | Walchand College of Engineering, Sangli | 2026–27  
> **Team:** Sahil Patil · Tenzin Dargyal · Pranav Chougule · Vrushabh Tonge  
> **Guide:** A.S. Pawar, Assistant Professor

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MONOREPO: /mega                             │
│                                                                     │
│  ┌──────────────┐   REST    ┌──────────────────┐   HTTP    ┌──────────────────┐ │
│  │   /frontend  │ ────────► │    /backend      │ ────────► │  /ml-service     │ │
│  │ React + Vite │          │  Node.js+Express  │           │  Python+FastAPI  │ │
│  └──────────────┘          └──────────────────┘           └──────────────────┘ │
│                                     │                              │            │
│                              ┌──────┴──────┐                       │            │
│                              │  MongoDB    │◄──────────────────────┘            │
│                              │  + Redis    │                                    │
│                              └─────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### How it works
1. User uploads a video → Node backend enqueues a BullMQ indexing job
2. Python ML service processes the video: segments → CLIP (visual) + Whisper (speech) + PaddleOCR (text) → FAISS
3. User types a natural language query → GQE expansion → FAISS retrieval → dynamic modality weighting → temporal localization
4. Frontend displays the video player **auto-seeking to the exact timestamp** with an evidence breakdown panel

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | ≥ 18 | https://nodejs.org |
| Python | ≥ 3.10 | https://python.org |
| Docker Desktop | ≥ 24 | https://docker.com |
| FFmpeg | any | `winget install ffmpeg` |
| Git | ≥ 2.40 | https://git-scm.com |

---

## Quick Start

### 1. Clone the repo
```bash
git clone <repo-url>
cd mega
```

### 2. Start infrastructure (MongoDB + Redis)
```bash
docker compose up -d
```

> **If you have MongoDB installed locally:** You can skip the `mongodb` service by running  
> `docker compose up -d redis` instead. Update `backend/.env` with your local connection string.

### 3. ML Service (Python)
```bash
cd ml-service
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies; chooses NVIDIA CUDA on Windows/Linux, otherwise CPU.
# Requires Python 3.10–3.12; Python 3.11 is recommended.
python install.py
cp .env.example .env      # Edit .env with your settings
uvicorn main:app --reload --port 8001
```
Whisper automatically uses MLX on Apple Silicon, PyTorch CUDA on NVIDIA
machines, and CPU otherwise. MLX downloads its matching model on first use.
Set `FORCE_CPU=true` to disable GPU use. `WHISPER_MLX_MODEL` optionally selects
an MLX model repository or local path. If MLX fails, transcription falls back
to CPU for the rest of that service session. `/ml/health` reports the active backend.

Indexing batches eight chunks and up to 32 CLIP inputs per model call, with
bulk MongoDB writes. `INDEXING_BATCH_SIZE` and `CLIP_BATCH_SIZE` control memory
usage; reduce these if GPU memory is limited. Chunk size (7s), overlap (3s),
four sampled frames, and OCR on every frame are retained. Pipeline logs report
segmentation, Whisper, CLIP, OCR, and database/FAISS timings to identify bottlenecks.
The ML service serializes indexing/reindexing and ignores duplicate submissions
for pending videos. Run one Uvicorn worker for this in-memory model/index setup.
Backend indexing waits up to two hours by default, including queue wait.

> ML service runs at **http://localhost:8001**  
> API docs: **http://localhost:8001/docs**

The trained modality weighting model loads from
`ml-service/weights/weighting_module.pt` at startup on CPU. Search defaults to
dynamic weighting; set `use_dynamic_weights: false` in a search request to use
fixed weights for comparison. `/ml/health` includes `weighting_model.loaded`
and the checkpoint path. Restart the ML service after replacing the checkpoint.
If the checkpoint cannot load, search falls back to fixed weights and reports
`weighting_mode: "fixed"`. The QVHighlights checkpoint uses the OpenAI
ViT-B-32 CLIP embedding space (`CLIP_MODEL_NAME=ViT-B-32`,
`CLIP_PRETRAINED=openai`).

Dynamic fusion reports `weighting_method: "query_intent_and_mlp_v3"`.
It combines 75% query intent (CLIP similarity to visual/speech/OCR descriptions,
complemented by the existing keyword classifier when explicit cues exist) with
25% checkpoint prediction. This is hybrid calibration, not checkpoint retraining:
the QVHighlights proxy-label checkpoint favors speech and has no OCR-dominant
training examples. Weighting encodes the original query even when GQE supplies
expanded embeddings, uses raw retrieval scores, and preserves relative weights
when a modality is unavailable.

Search cache v4 and expansion cache v2 bypass earlier inaccurate results.
Expansion rejects generated code, repeated phrases and verbose answers, and
always retains the original query. Expansions propose candidates; final cosine
scores use the original query across all candidate modalities. Transcript/OCR
topic matches add candidates and contribute half of each text-modality score.
Deleted or unowned videos are excluded before ranking. Seven-second matches
retain their indexed timestamps; longer visual refinement uses stored start/end
times, and playback context is clamped to the video's duration. Similarity
scores are displayed as scores rather than a probability of a correct match.

The standalone OCR benchmarks and recorded results live in
[`ocr-optimization/`](./ocr-optimization/RESULTS.md), inside this repository.
The benchmark supports configurable frame/model paths; the application imports
its runtime detector helper from `ml-service/app/services/ocr_acceleration.py`.

### 4. Backend (Node.js)

```bash
cd backend
npm install
cp .env.example .env      # Edit .env with your settings
npm run dev
```
> Backend runs at **http://localhost:3000**

### 5. Frontend (React + Vite)
```bash
cd frontend
npm install
cp .env.example .env      # Edit .env with your settings
npm run dev
```
> Frontend runs at **http://localhost:5173**

---

## API Contract

### Node.js Backend → Frontend

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login, returns JWT |
| `POST` | `/api/videos/upload` | Upload a video (multipart) |
| `GET` | `/api/videos` | List all indexed videos |
| `GET` | `/api/videos/:id/status` | Poll indexing status |
| `POST` | `/api/search` | Semantic video search |

### FastAPI ML Service (internal)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/ml/health` | Liveness probe |
| `POST` | `/ml/index` | Trigger offline indexing for a video |
| `POST` | `/ml/search` | Run full online query pipeline |
| `POST` | `/ml/query/expand` | GQE-style query expansion |

Full OpenAPI spec: [`ml-service/openapi.yaml`](./ml-service/openapi.yaml)

---

## MongoDB Schemas

| Collection | Description |
|------------|-------------|
| `videos` | Video metadata + indexing status |
| `segments` | Per-chunk embeddings + transcript + OCR text |
| `queries` | Query cache (raw + expanded variants) |
| `results` | Search results with evidence breakdown |

---

## Team Structure

| Member | Role | Service |
|--------|------|---------|
| Sahil Patil | ML Service Lead | `/ml-service` |
| Tenzin Dargyal | Query Pipeline | `/ml-service/app/routes/query*` |
| Pranav Chougule | Backend Lead | `/backend` |
| Vrushabh Tonge | Frontend Lead | `/frontend` |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + Vite + TypeScript |
| Backend | Node.js 18 + Express + BullMQ + Mongoose |
| ML Service | Python 3.10 + FastAPI + Uvicorn |
| Visual Embeddings | CLIP / OpenCLIP (ViT-B/32 or ViT-L/14) |
| Speech | OpenAI Whisper |
| OCR | PaddleOCR |
| Query Expansion | flan-t5-base (local) / GPT-3.5 (API) |
| Vector Search | FAISS (CPU; GPU auto-detected) |
| Database | MongoDB 7 |
| Queue | Redis 7 + BullMQ |
| Evaluation | QVHighlights, Charades-STA |
