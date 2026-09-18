"""
Whisper ASR Service.

Transcribes video audio and maps word-level transcript segments to video chunks.
Model is loaded once and cached for reuse across pipeline calls.
"""
from functools import lru_cache
from typing import Dict, List

import whisper

from app.config import get_settings
from app.services.segmentation import ChunkInfo

settings = get_settings()


@lru_cache(maxsize=1)
def get_whisper_model():
    """Lazy-load and cache the Whisper model."""
    print(f"[Whisper] Loading model '{settings.whisper_model_size}' on {settings.device}...")
    model = whisper.load_model(settings.whisper_model_size, device=settings.device)
    print("[Whisper] Model loaded.")
    return model


def transcribe_video(video_path: str) -> List[Dict]:
    """
    Transcribe the full video and return word-level segments.

    Returns:
        List of dicts: [{ 'start': float, 'end': float, 'text': str }, ...]
    """
    model = get_whisper_model()

    result = model.transcribe(
        video_path,
        word_timestamps=True,
        verbose=False,
        fp16=False,  # fp16 not supported on CPU
    )

    # Flatten word-level segments from all top-level segments
    segments: List[Dict] = []
    for seg in result.get("segments", []):
        # Use word-level if available
        words = seg.get("words", [])
        if words:
            for word in words:
                segments.append({
                    "start": word["start"],
                    "end": word["end"],
                    "text": word["word"].strip(),
                })
        else:
            # Fallback to segment-level
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            })

    return segments


def map_transcript_to_chunks(
    transcript_segments: List[Dict],
    chunks: List[ChunkInfo],
) -> Dict[int, str]:
    """
    Map transcript words/segments to video chunks by timestamp overlap.

    A transcript segment is assigned to a chunk if its midpoint falls within
    [chunk.start_time, chunk.end_time].

    Returns:
        Dict mapping chunk_id → transcript text string (empty string if no speech).
    """
    chunk_transcripts: Dict[int, List[str]] = {c.chunk_id: [] for c in chunks}

    for seg in transcript_segments:
        seg_mid = (seg["start"] + seg["end"]) / 2
        for chunk in chunks:
            if chunk.start_time <= seg_mid < chunk.end_time:
                chunk_transcripts[chunk.chunk_id].append(seg["text"])
                break  # Each segment assigned to exactly one chunk

    return {
        chunk_id: " ".join(words).strip()
        for chunk_id, words in chunk_transcripts.items()
    }
