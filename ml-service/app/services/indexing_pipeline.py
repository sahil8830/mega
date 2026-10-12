"""
Offline Indexing Pipeline Orchestrator.

Wires segmentation -> CLIP -> Whisper -> PaddleOCR -> FAISS -> MongoDB.
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
from time import perf_counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import sys
import numpy as np
from PIL import Image
from bson import ObjectId
from pymongo import UpdateOne

# Force UTF-8 output so Unicode chars don't crash on Windows cp1252 terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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
    user_id: str = "global",
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
        started = stage_started = perf_counter()
        chunks: List[ChunkInfo] = segment_video(
            video_path=video_path,
            chunk_size=settings.chunk_size_seconds,
            overlap=settings.chunk_overlap_seconds,
            n_frames=settings.frames_per_chunk,
        )

        print(f"[Pipeline]   -> {len(chunks)} chunks created in {perf_counter() - stage_started:.1f}s")
        stage_started = perf_counter()

        # ── Step 2: Whisper ASR (full video, then map to chunks) ───────────────
        print("[Pipeline] Step 2/5: Whisper transcription...")
        transcript_segments = transcribe_video(video_path)
        chunk_transcripts: Dict[int, str] = map_transcript_to_chunks(
            transcript_segments, chunks
        )
        non_empty = sum(1 for t in chunk_transcripts.values() if t)
        print(f"[Pipeline]   -> {len(transcript_segments)} words transcribed, "
              f"{non_empty}/{len(chunks)} chunks have speech")

        print(f"[Pipeline] Whisper: {perf_counter() - stage_started:.1f}s")

        # ── Steps 3a-g: Per-chunk processing ───────────────────────────────────
        print(f"[Pipeline] Step 3/5: Processing {len(chunks)} chunks (CLIP + OCR + FAISS + MongoDB)...")
        faiss_mgr = get_faiss_manager(user_id)
        timings = {"clip": 0.0, "ocr": 0.0, "database": 0.0}
        for offset in range(0, len(chunks), settings.indexing_batch_size):
            batch = chunks[offset:offset + settings.indexing_batch_size]
            await _process_batch(batch, chunk_transcripts, video_id, db, faiss_mgr, timings)
            done = offset + len(batch)
            print(f"[Pipeline][{video_id}]   -> {done}/{len(chunks)} chunks done "
                  f"(CLIP {timings['clip']:.1f}s, OCR {timings['ocr']:.1f}s, "
                  f"database/FAISS {timings['database']:.1f}s)")

        print(f"[Pipeline]   -> All {len(chunks)} chunks processed")

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
        print(f"\n[Pipeline] DONE! {len(chunks)} segments indexed in {perf_counter() - started:.1f}s.")
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
        print(f"[Pipeline] ERROR: {error_msg}")
        await _update_video_status(db, video_id, "failed", str(e))
        # Attempt cleanup even on failure
        try:
            cleanup_chunk_frames(video_path)
        except Exception:
            pass
        return IndexingResult(video_id=video_id, status="failed", error=str(e))


async def _process_batch(chunks, transcripts, video_id, db, faiss_mgr, timings):
    """Batch CLIP inference and MongoDB writes; retain each chunk's timestamps."""
    visual = {chunk.chunk_id: np.zeros(512, dtype=np.float32) for chunk in chunks}
    images, owners = [], []
    embeddings = {chunk.chunk_id: [] for chunk in chunks}
    clip_started = perf_counter()

    def encode_pending():
        if images:
            vectors = encode_images(images)
            for owner, vector in zip(owners, vectors):
                embeddings[owner].append(vector)
            for image in images:
                image.close()
            images.clear()
            owners.clear()

    for chunk in chunks:
        for path in chunk.frame_paths:
            try:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
                owners.append(chunk.chunk_id)
            except (OSError, ValueError):
                continue
            if len(images) >= settings.clip_batch_size:
                encode_pending()
    encode_pending()
    for chunk_id, vectors in embeddings.items():
        if vectors:
            visual[chunk_id] = mean_pool(np.stack(vectors))
    timings["clip"] += perf_counter() - clip_started

    ocr_started = perf_counter()
    ocr_texts = [extract_text_from_chunk(chunk.frame_paths) for chunk in chunks]
    timings["ocr"] += perf_counter() - ocr_started
    speech_texts = [transcripts.get(chunk.chunk_id, "") for chunk in chunks]
    prompts = [f"A sports commentator says: {text.strip()}" if text.strip() else ""
               for text in speech_texts]
    prompts += [f"On-screen text reads: {text.strip()}" if text.strip() else ""
                for text in ocr_texts]
    clip_started = perf_counter()
    text_vectors = []
    for offset in range(0, len(prompts), settings.clip_batch_size):
        text_vectors.extend(encode_texts(prompts[offset:offset + settings.clip_batch_size]))
    timings["clip"] += perf_counter() - clip_started

    database_started = perf_counter()
    docs = []
    for i, chunk in enumerate(chunks):
        docs.append({
            "_id": ObjectId(), "videoId": ObjectId(video_id),
            "chunkId": chunk.chunk_id, "startTime": chunk.start_time,
            "endTime": chunk.end_time, "framePaths": chunk.frame_paths,
            "visualEmbedding": visual[chunk.chunk_id].tolist(),
            "transcript": speech_texts[i], "speechEmbedding": text_vectors[i].tolist(),
            "ocrText": ocr_texts[i], "ocrEmbedding": text_vectors[len(chunks) + i].tolist(),
            "faissVisualId": None, "faissSpeechId": None, "faissOcrId": None,
            "createdAt": datetime.now(timezone.utc),
        })
    await db["segments"].insert_many(docs)
    updates = []
    for i, (chunk, doc) in enumerate(zip(chunks, docs)):
        ids = faiss_mgr.add_segment(
            visual_emb=visual[chunk.chunk_id], speech_emb=text_vectors[i],
            ocr_emb=text_vectors[len(chunks) + i], video_id=video_id,
            segment_id=str(doc["_id"]), chunk_id=chunk.chunk_id,
            start_time=chunk.start_time, end_time=chunk.end_time,
        )
        updates.append(UpdateOne({"_id": doc["_id"]}, {"$set": {
            "faissVisualId": ids["visual_id"], "faissSpeechId": ids["speech_id"],
            "faissOcrId": ids["ocr_id"],
        }}))
    await db["segments"].bulk_write(updates)
    timings["database"] += perf_counter() - database_started
    return [str(doc["_id"]) for doc in docs]


async def _process_chunk(chunk, transcript, video_id, db, faiss_mgr):
    """Compatibility wrapper for callers processing a single chunk."""
    ids = await _process_batch([chunk], {chunk.chunk_id: transcript}, video_id, db,
                               faiss_mgr, {"clip": 0.0, "ocr": 0.0, "database": 0.0})
    return ids[0]


async def _update_video_status(db, video_id: str, status: str, error: str = None):
    """Update the Video document status in MongoDB."""
    update = {"$set": {"status": status, "updatedAt": datetime.now(timezone.utc)}}
    if error:
        update["$set"]["errorMessage"] = error
    await db["videos"].update_one({"_id": ObjectId(video_id)}, update)
