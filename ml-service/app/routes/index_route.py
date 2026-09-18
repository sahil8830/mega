"""
POST /ml/index — Trigger offline indexing pipeline for a video.

The pipeline is run as a FastAPI BackgroundTask so the HTTP response
returns immediately with status="indexing". The BullMQ worker polls
GET /api/videos/:id/status to detect completion.
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class IndexRequest(BaseModel):
    video_id: str
    video_filename: str


class IndexResponse(BaseModel):
    video_id: str
    status: str
    message: str


async def _pipeline_task(video_id: str, video_filename: str):
    """Background task wrapper — imports pipeline lazily to keep server startup fast."""
    from app.services.indexing_pipeline import run_indexing_pipeline
    await run_indexing_pipeline(video_id=video_id, video_filename=video_filename)


@router.post("/ml/index", response_model=IndexResponse, tags=["Indexing"])
async def index_video(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Trigger the offline indexing pipeline for a single video.

    Returns immediately with status='indexing'.
    Poll GET /api/videos/:id/status on the Node backend to check completion.

    Pipeline steps (runs in background):
      1. Temporal segmentation (ffprobe + OpenCV)
      2. Whisper ASR transcription
      3. Per-chunk: CLIP visual embedding + speech embedding + OCR + FAISS
      4. Save FAISS indices to disk
      5. Cleanup temp frames
      6. Update MongoDB Video status → 'indexed'
    """
    background_tasks.add_task(
        _pipeline_task,
        video_id=request.video_id,
        video_filename=request.video_filename,
    )

    return IndexResponse(
        video_id=request.video_id,
        status="indexing",
        message="Indexing pipeline started in background. Poll /api/videos/:id/status for completion.",
    )
