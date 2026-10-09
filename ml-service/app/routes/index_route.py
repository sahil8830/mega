"""
POST /ml/index  — Trigger offline indexing pipeline for a video.
POST /ml/reindex — Clear existing FAISS entries for a video, then re-index
                   with the latest improved settings.

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


async def _reindex_task(video_id: str, video_filename: str, user_id: str):
    """Clear existing FAISS entries for this video, then re-run the pipeline."""
    from app.services.faiss_manager import get_faiss_manager
    from app.services.indexing_pipeline import run_indexing_pipeline
    from app.db import get_db

    # 1. Remove old FAISS entries for this video
    faiss_mgr = get_faiss_manager(user_id)
    faiss_mgr.reset_for_video(video_id)

    # 2. Reset video status in MongoDB to 'queued' so pipeline can update it
    db = get_db()
    from bson import ObjectId
    from datetime import datetime, timezone
    await db["videos"].update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {"status": "indexing", "updatedAt": datetime.now(timezone.utc)}},
    )

    # 3. Delete old segment documents for this video
    await db["segments"].delete_many({"videoId": ObjectId(video_id)})

    # 4. Run fresh indexing pipeline
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


@router.post("/ml/reindex", response_model=IndexResponse, tags=["Indexing"])
async def reindex_video(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Re-index a video with the latest improved settings.

    Clears all existing FAISS entries and segment documents for this video,
    then runs the full pipeline fresh (7s chunks, 4 frames, prompt-wrapped embeddings).

    Returns immediately. Poll /api/videos/:id/status for completion.
    """
    background_tasks.add_task(
        _reindex_task,
        video_id=request.video_id,
        video_filename=request.video_filename,
        user_id=request.user_id,
    )

    return IndexResponse(
        video_id=request.video_id,
        status="reindexing",
        message=f"Re-indexing started for video {request.video_id}. Old data cleared. Poll /api/videos/:id/status.",
    )


class DeleteVideoRequest(BaseModel):
    video_id: str
    user_id: str = 'global'


@router.post('/ml/delete-video', tags=['Indexing'])
async def delete_video_index(request: DeleteVideoRequest):
    import asyncio
    from app.services.faiss_manager import get_faiss_manager

    faiss_mgr = get_faiss_manager(request.user_id)

    # FAISS rebuild is CPU-bound/blocking — run in thread so event loop isn't blocked
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, faiss_mgr.reset_for_video, request.video_id)

    return {'message': f'FAISS entries cleared for video {request.video_id}'}

