from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class IndexRequest(BaseModel):
    video_id: str
    video_filename: str


class IndexResponse(BaseModel):
    video_id: str
    status: str
    message: str


@router.post("/ml/index", response_model=IndexResponse, tags=["Indexing"])
async def index_video(request: IndexRequest):
    """
    Trigger the offline indexing pipeline for a single video.

    Pipeline (Phase 1 implementation):
      1. Temporal segmentation (FFmpeg)
      2. Representative frame sampling (OpenCV)
      3. Visual embedding extraction (CLIP)
      4. Speech transcription (Whisper)
      5. OCR text extraction (PaddleOCR)
      6. FAISS index update + MongoDB segment storage

    Currently returns a stub response — full implementation in Phase 1.
    """
    # TODO (Phase 1): implement full indexing pipeline
    return IndexResponse(
        video_id=request.video_id,
        status="stub",
        message="Indexing pipeline not yet implemented — Phase 1 work.",
    )
