from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.routes.health import router as health_router
from app.routes.index_route import router as index_router
from app.routes.search_route import router as search_router
from app.routes.query_route import router as query_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Ensure storage directories exist
    os.makedirs(settings.faiss_index_path, exist_ok=True)
    os.makedirs(settings.video_storage_path, exist_ok=True)

    print("==> ML Service ready")
    print(f"    Device   : {settings.device.upper()}")
    print(f"    CLIP     : {settings.clip_model_name} ({settings.clip_pretrained})")
    print(f"    Whisper  : {settings.whisper_model_size}")
    print(f"    FAISS dir: {settings.faiss_index_path}")
    print(f"    MongoDB  : {settings.mongodb_uri}")
    print("    Models load lazily on first request")

    yield  # Application is running

    print("==> ML Service shutting down")





app = FastAPI(
    title="Mega ML Service",
    description=(
        "AI/ML backend for Universal Semantic Video Search & Moment Retrieval. "
        "Handles CLIP visual embeddings, Whisper ASR, PaddleOCR, FAISS indexing, "
        "GQE query expansion, dynamic modality weighting, and temporal localization."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(index_router)
app.include_router(search_router)
app.include_router(query_router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Mega ML Service",
        "docs": "/docs",
        "health": "/ml/health",
    }
