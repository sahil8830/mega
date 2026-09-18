"""
Offline Indexing Pipeline Orchestrator.

Wires segmentation → CLIP → Whisper → PaddleOCR → FAISS → MongoDB.
Called by POST /ml/index as a FastAPI BackgroundTask.

Pipeline steps:
  1. Temporal segmentation  (segmentation.py)
  2. Whisper ASR on full video  (whisper_asr.py)
  3. For each chunk:
       a. Load frame images
       b. CLIP visual embedding  (clip_model.py)
       c. CLIP text embedding for transcript  (clip_model.py)
       d. OCR text extraction  (ocr_service.py)
       e. CLIP text embedding for OCR  (clip_model.py)
       f. Add to FAISS  (faiss_manager.py)
       g. Insert Segment document to MongoDB  (db.py)
  4. Save FAISS indices to disk
  5. Cleanup extracted frames
  6. Update Video status in MongoDB
"""
import os
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image
from bson import ObjectId

from app.config import get_settings
from app.db import get_db
from app.services.clip_model import encode_images, encode_texts, mean_pool
from app.services.faiss_manager import get_faiss_manager
from app.services.ocr_service import extract_text_from_chunk
from app.services.segmentation import ChunkInfo, cleanup_chunk_frames, segment_video
from app.services.whisper_asr import map_transcript_to_chunks, transcribe_video

settings = get_settings()


@dataclass
class IndexingResult:
    video_id: str
    status: str                  # "indexed" | "failed"
    num_chunks: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    faiss_stats: Dict = None


async def run_indexing_pipeline(
    video_id: str,
    video_filename: str,
) -> IndexingResult:
    """
    Full offline indexing pipeline for a single video.
    Updates MongoDB Video status throughout.
    """
    db = get_db()
    video_path = str(Path(settings.video_storage_path) / video_filename)

    if not os.path.exists(video_path):
        err = f"Video file not found: {video_path}"
        await _update_video_status(db, video_id, "failed", err)
        return IndexingResult(video_id=video_id, status="failed", error=err)

    await _update_video_status(db, video_id, "indexing")
    print(f"\n{'='*60}")
    print(f"[Pipeline] Starting indexing for video: {video_id}")
    print(f"[Pipeline] File: {video_path}")
    print(f"{'='*60}")

    try:
        # ── Step 1: Temporal Segmentation ──────────────────────────────────────
        print("[Pipeline] Step 1/5: Temporal segmentation...")
        chunks: List[ChunkInfo] = segment_video(
            video_path=video_path,
            chunk_size=int(os.getenv("CHUNK_SIZE_SECONDS", "10")),
            overlap=int(os.getenv("CHUNK_OVERLAP_SECONDS", "2")),
            n_frames=int(os.getenv("FRAMES_PER_CHUNK", "2")),
        )
        print(f"[Pipeline]   → {len(chunks)} chunks created")

        # ── Step 2: Whisper ASR (full video, then map to chunks) ───────────────
        print("[Pipeline] Step 2/5: Whisper transcription...")
        transcript_segments = transcribe_video(video_path)
        chunk_transcripts: Dict[int, str] = map_transcript_to_chunks(
            transcript_segments, chunks
        )
        non_empty = sum(1 for t in chunk_transcripts.values() if t)
        print(f"[Pipeline]   → {len(transcript_segments)} words transcribed, "
              f"{non_empty}/{len(chunks)} chunks have speech")

        # ── Steps 3a-g: Per-chunk processing ───────────────────────────────────
        print(f"[Pipeline] Step 3/5: Processing {len(chunks)} chunks (CLIP + OCR + FAISS + MongoDB)...")
        faiss_mgr = get_faiss_manager()
        inserted_ids = []

        for chunk in chunks:
            segment_doc = await _process_chunk(
                chunk=chunk,
                transcript=chunk_transcripts.get(chunk.chunk_id, ""),
                video_id=video_id,
                db=db,
                faiss_mgr=faiss_mgr,
            )
            inserted_ids.append(segment_doc)

            if (chunk.chunk_id + 1) % 5 == 0:
                print(f"[Pipeline]   → {chunk.chunk_id + 1}/{len(chunks)} chunks done")

        print(f"[Pipeline]   → All {len(chunks)} chunks processed")

        # ── Step 4: Save FAISS indices ─────────────────────────────────────────
        print("[Pipeline] Step 4/5: Saving FAISS indices...")
        faiss_mgr.save()

        # ── Step 5: Cleanup frames + update Video status ───────────────────────
        print("[Pipeline] Step 5/5: Cleaning up frames...")
        cleanup_chunk_frames(video_path)

        # Get video duration from first/last chunk
        duration = chunks[-1].end_time if chunks else 0.0
        await db["videos"].update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {
                "status": "indexed",
                "duration": duration,
                "updatedAt": datetime.now(timezone.utc),
            }},
        )

        stats = faiss_mgr.stats()
        print(f"\n[Pipeline] ✅ Done! {len(chunks)} segments indexed.")
        print(f"[Pipeline] FAISS: visual={stats['visual_count']} "
              f"speech={stats['speech_count']} ocr={stats['ocr_count']}")

        return IndexingResult(
            video_id=video_id,
            status="indexed",
            num_chunks=len(chunks),
            duration_seconds=duration,
            faiss_stats=stats,
        )

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"[Pipeline] ❌ Error: {error_msg}")
        await _update_video_status(db, video_id, "failed", str(e))
        # Attempt cleanup even on failure
        try:
            cleanup_chunk_frames(video_path)
        except Exception:
            pass
        return IndexingResult(video_id=video_id, status="failed", error=str(e))


async def _process_chunk(
    chunk: ChunkInfo,
    transcript: str,
    video_id: str,
    db,
    faiss_mgr,
) -> str:
    """
    Process a single chunk: visual embedding → speech embedding → OCR → FAISS → MongoDB.
    Returns the MongoDB inserted segment _id as string.
    """
    # ── Visual embedding ────────────────────────────────────────────────────────
    frame_images = []
    for path in chunk.frame_paths:
        try:
            frame_images.append(Image.open(path).convert("RGB"))
        except Exception:
            pass  # Skip unreadable frames

    if frame_images:
        frame_embs = encode_images(frame_images)        # (N, 512)
        visual_emb = mean_pool(frame_embs)              # (512,)
    else:
        visual_emb = np.zeros(512, dtype=np.float32)

    # ── Speech embedding (CLIP text encoder on transcript) ─────────────────────
    speech_embs = encode_texts([transcript])            # (1, 512)
    speech_emb = speech_embs[0]                        # (512,) — zero if empty

    # ── OCR text + OCR embedding ───────────────────────────────────────────────
    ocr_text = extract_text_from_chunk(chunk.frame_paths)
    ocr_embs = encode_texts([ocr_text])                 # (1, 512)
    ocr_emb = ocr_embs[0]                              # (512,) — zero if empty

    # ── Insert Segment to MongoDB first (to get _id for FAISS metadata) ────────
    segment_doc = {
        "videoId": ObjectId(video_id),
        "chunkId": chunk.chunk_id,
        "startTime": chunk.start_time,
        "endTime": chunk.end_time,
        "framePaths": chunk.frame_paths,
        "visualEmbedding": visual_emb.tolist(),
        "transcript": transcript,
        "speechEmbedding": speech_emb.tolist(),
        "ocrText": ocr_text,
        "ocrEmbedding": ocr_emb.tolist(),
        "faissVisualId": None,
        "faissSpeechId": None,
        "faissOcrId": None,
        "createdAt": datetime.now(timezone.utc),
    }
    result = await db["segments"].insert_one(segment_doc)
    segment_id = str(result.inserted_id)

    # ── Add to FAISS indices ────────────────────────────────────────────────────
    faiss_ids = faiss_mgr.add_segment(
        visual_emb=visual_emb,
        speech_emb=speech_emb,
        ocr_emb=ocr_emb,
        video_id=video_id,
        segment_id=segment_id,
        chunk_id=chunk.chunk_id,
        start_time=chunk.start_time,
        end_time=chunk.end_time,
    )

    # ── Update segment with FAISS IDs ──────────────────────────────────────────
    await db["segments"].update_one(
        {"_id": result.inserted_id},
        {"$set": {
            "faissVisualId": faiss_ids["visual_id"],
            "faissSpeechId": faiss_ids["speech_id"],
            "faissOcrId": faiss_ids["ocr_id"],
        }},
    )

    return segment_id


async def _update_video_status(db, video_id: str, status: str, error: str = None):
    """Update the Video document status in MongoDB."""
    update = {"$set": {"status": status, "updatedAt": datetime.now(timezone.utc)}}
    if error:
        update["$set"]["errorMessage"] = error
    await db["videos"].update_one({"_id": ObjectId(video_id)}, update)
