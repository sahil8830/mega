# Phase 0 — Tasks

## Root Monorepo
- [x] `.gitignore`
- [x] `docker-compose.yml`
- [x] `README.md`

## ML Service (Python + FastAPI)
- [x] `ml-service/requirements.txt`
- [x] `ml-service/.env.example`
- [x] `ml-service/main.py`
- [x] `ml-service/app/__init__.py`
- [x] `ml-service/app/config.py`
- [x] `ml-service/app/routes/__init__.py`
- [x] `ml-service/app/routes/health.py`
- [x] `ml-service/app/routes/index_route.py`
- [x] `ml-service/app/routes/search_route.py`
- [x] `ml-service/app/routes/query_route.py`
- [x] `ml-service/openapi.yaml`

## Backend (Node.js + Express)
- [x] `backend/package.json`
- [x] `backend/.env.example`
- [x] `backend/src/index.js`
- [x] `backend/src/config/db.js`
- [x] `backend/src/models/Video.js`
- [x] `backend/src/models/Segment.js`
- [x] `backend/src/models/Query.js`
- [x] `backend/src/models/Result.js`
- [x] `backend/src/models/User.js`
- [x] `backend/src/routes/videos.js`
- [x] `backend/src/routes/search.js`
- [x] `backend/src/routes/auth.js`
- [x] `backend/src/middleware/auth.js`
- [x] `backend/src/queues/indexingQueue.js`
- [x] `backend/storage/videos/.gitkeep`
- [x] `npm install` — 192 packages, 0 vulnerabilities

## Frontend (React + Vite)
- [x] Scaffold via `npx create vite@latest` (react-ts template)
- [x] `frontend/.env.example`
- [x] Stub pages: UploadPage, SearchPage, ResultPage
- [x] `npm install` — 16 packages, 0 vulnerabilities

## Verification
- [x] MongoDB connection: OK (localhost)
- [x] Redis connection: OK (PONG)
