"""
Temporal Segmentation Service.

Splits a video into overlapping fixed-length chunks and samples representative frames.
Uses ffprobe for duration detection and OpenCV for frame extraction.
"""
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import cv2
from PIL import Image

from app.config import get_settings

settings = get_settings()

# Frames are saved here during indexing (gitignored)
FRAMES_DIR = Path(__file__).parent.parent.parent / "frames"
FRAMES_DIR.mkdir(exist_ok=True)


@dataclass
class ChunkInfo:
    chunk_id: int
    start_time: float       # seconds
    end_time: float         # seconds
    frame_paths: List[str] = field(default_factory=list)


def get_video_duration(video_path: str) -> float:
    """
    Use ffprobe to get the duration of a video in seconds.
    Raises RuntimeError if ffprobe is not available or the file is unreadable.
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, ValueError) as e:
        raise RuntimeError(f"ffprobe failed for {video_path}: {e}") from e


def segment_video(
    video_path: str,
    chunk_size: int = 10,
    overlap: int = 2,
    n_frames: int = 2,
) -> List[ChunkInfo]:
    """
    Split a video into overlapping chunks and extract representative frames.

    Args:
        video_path: Absolute path to the video file.
        chunk_size: Length of each chunk in seconds (default 10s).
        overlap: Overlap between consecutive chunks in seconds (default 2s).
        n_frames: Number of frames to sample per chunk (default 2).

    Returns:
        List of ChunkInfo objects, one per chunk.
    """
    duration = get_video_duration(video_path)
    step = chunk_size - overlap
    chunks: List[ChunkInfo] = []

    video_stem = Path(video_path).stem
    chunk_frame_dir = FRAMES_DIR / video_stem
    chunk_frame_dir.mkdir(parents=True, exist_ok=True)

    t = 0.0
    chunk_id = 0

    while t < duration:
        start = t
        end = min(t + chunk_size, duration)

        frame_paths = _extract_frames(
            video_path=video_path,
            start=start,
            end=end,
            n_frames=n_frames,
            output_dir=chunk_frame_dir,
            chunk_id=chunk_id,
        )

        chunks.append(ChunkInfo(
            chunk_id=chunk_id,
            start_time=round(start, 3),
            end_time=round(end, 3),
            frame_paths=frame_paths,
        ))

        chunk_id += 1
        t += step

        # If the remaining segment is shorter than overlap, stop
        if end >= duration:
            break

    return chunks


def _extract_frames(
    video_path: str,
    start: float,
    end: float,
    n_frames: int,
    output_dir: Path,
    chunk_id: int,
) -> List[str]:
    """
    Extract n_frames evenly-spaced frames from [start, end] using OpenCV.

    Returns list of absolute paths to saved frame images.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration = end - start

    if n_frames == 1:
        sample_offsets = [duration / 2]
    else:
        # Evenly spaced: e.g., for 2 frames: [10%, 90%] of the chunk
        sample_offsets = [
            duration * (i + 1) / (n_frames + 1)
            for i in range(n_frames)
        ]

    saved_paths: List[str] = []

    for i, offset in enumerate(sample_offsets):
        target_time = start + offset
        target_frame = int(target_time * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()

        if not ret:
            # Try the nearest readable frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, target_frame - 1))
            ret, frame = cap.read()

        if ret:
            # Convert BGR → RGB and save as JPEG
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            out_path = str(output_dir / f"chunk{chunk_id:04d}_frame{i}.jpg")
            pil_img.save(out_path, quality=90)
            saved_paths.append(out_path)

    cap.release()
    return saved_paths


def cleanup_chunk_frames(video_path: str) -> None:
    """
    Remove all extracted frames for a video after indexing is complete.
    Call this after the FAISS index and MongoDB are updated.
    """
    import shutil
    video_stem = Path(video_path).stem
    chunk_frame_dir = FRAMES_DIR / video_stem
    if chunk_frame_dir.exists():
        shutil.rmtree(chunk_frame_dir)
