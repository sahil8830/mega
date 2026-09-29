"""
POST /ml/index — Trigger offline indexing pipeline for a video.

Now accepts user_id so each user's videos are indexed into their own
isolated FAISS index namespace (faiss/{user_id}/).
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class IndexRequest(BaseModel):
    video_id: str
    video_filename: str
    user_id: str = "global"   # user's MongoDB _id string


class IndexResponse(BaseModel):
    video_id: str
    status: str
    message: str


async def _pipeline_task(video_id: str, video_filename: str, user_id: str):
    """Background task wrapper — imports pipeline lazily to keep server startup fast."""
    from app.services.indexing_pipeline import run_indexing_pipeline
    await run_indexing_pipeline(
        video_id=video_id,
        video_filename=video_filename,
        user_id=user_id,
    )


@router.post("/ml/index", response_model=IndexResponse, tags=["Indexing"])
async def index_video(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Trigger the offline indexing pipeline for a single video.

    Returns immediately with status='indexing'.
    Poll GET /api/videos/:id/status on the Node backend to check completion.

    The video is indexed into a per-user FAISS namespace (faiss/{user_id}/)
    so each user's search space is fully isolated.
    """
    background_tasks.add_task(
        _pipeline_task,
        video_id=request.video_id,
        video_filename=request.video_filename,
        user_id=request.user_id,
    )

    return IndexResponse(
        video_id=request.video_id,
        status="indexing",
        message=f"Indexing pipeline started for user {request.user_id}. Poll /api/videos/:id/status for completion.",
    )
