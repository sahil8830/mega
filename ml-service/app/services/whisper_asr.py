"""
Whisper ASR Service.

Transcribes video audio and maps word-level transcript segments to video chunks.
Model is loaded once and cached for reuse across pipeline calls.
"""
import os
import shutil
from functools import lru_cache
from typing import Dict, List

import whisper

from app.config import get_settings
from app.services.segmentation import ChunkInfo

settings = get_settings()


def _ensure_ffmpeg_in_path() -> None:
    """
    Whisper's audio.py calls `ffmpeg` via subprocess to decode audio.
    imageio-ffmpeg ships the binary as 'ffmpeg-win-x86_64-vX.Y.exe' (versioned name).
    Windows PATH lookup requires the exact name 'ffmpeg.exe', so we copy it.
    """
    if shutil.which("ffmpeg"):
        return  # Already available system-wide

    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()          # e.g. ffmpeg-win-x86_64-v7.1.exe
        ffmpeg_dir = os.path.dirname(src)
        dst = os.path.join(ffmpeg_dir, "ffmpeg.exe")   # the name subprocess/whisper looks for

        if not os.path.exists(dst):
            import shutil as _shutil
            _shutil.copy2(src, dst)
            print(f"[Whisper] Created ffmpeg.exe from {os.path.basename(src)}")

        # Add dir to PATH so subprocess can find ffmpeg.exe
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            print(f"[Whisper] Added ffmpeg dir to PATH: {ffmpeg_dir}")

    except Exception as e:
        print(f"[Whisper] WARNING: Could not set up ffmpeg ({e}). Transcription may fail.")


# Inject ffmpeg into PATH immediately at import time
_ensure_ffmpeg_in_path()


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

    # Step 1: Detect language first with a quick 30-sec probe
    audio = whisper.load_audio(video_path)
    audio_probe = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(audio_probe).to(model.device)
    _, probs = model.detect_language(mel)
    detected_lang = max(probs, key=probs.get)
    print(f"[Whisper] Detected language: {detected_lang}")

    # Step 2: If non-English, use task="translate" so CLIP gets English text
    # This means Hindi/Urdu/etc. speech becomes English → CLIP can match it
    task = "translate" if detected_lang != "en" else "transcribe"
    if task == "translate":
        print(f"[Whisper] Non-English audio ({detected_lang}) → translating to English for CLIP")

    result = model.transcribe(
        video_path,
        word_timestamps=True,
        verbose=False,
        fp16=False,        # fp16 not supported on CPU
        task=task,         # "transcribe" for English, "translate" for everything else
        language=detected_lang,
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
        Dict mapping chunk_id -> transcript text string (empty string if no speech).
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
