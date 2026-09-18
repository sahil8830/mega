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

pip install -r requirements.txt
cp .env.example .env      # Edit .env with your settings
uvicorn main:app --reload --port 8001
```
> ML service runs at **http://localhost:8001**  
> API docs: **http://localhost:8001/docs**

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
