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


def _get_ffprobe_binary() -> str:
    """Return path to ffprobe: system PATH -> imageio-ffmpeg bundled binary."""
    import shutil
    sys_ffprobe = shutil.which("ffprobe")
    if sys_ffprobe:
        return sys_ffprobe
    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_bin = str(ffmpeg_bin).replace("ffmpeg", "ffprobe")
        if os.path.exists(ffprobe_bin):
            return ffprobe_bin
        return ffmpeg_bin  # some bundles only ship ffmpeg; it can also probe
    except Exception:
        pass
    raise RuntimeError("ffprobe not found. Run: pip install imageio-ffmpeg")


def get_video_duration(video_path: str) -> float:
    """
    Get the duration of a video in seconds.
    Tries ffprobe first (system or imageio-ffmpeg bundled), then OpenCV.
    """
    try:
        ffprobe = _get_ffprobe_binary()
        cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
    except Exception as e:
        print(f"[Segmentation] ffprobe failed ({e}), falling back to OpenCV")

    # Fallback: OpenCV frame count / FPS
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if frames > 0 and fps > 0:
        dur = frames / fps
        print(f"[Segmentation] OpenCV duration estimate: {dur:.1f}s")
        return dur
    raise RuntimeError(f"Cannot determine duration for: {video_path}")


def segment_video(
    video_path: str,
    chunk_size: int = 7,
    overlap: int = 3,
    n_frames: int = 4,
) -> List[ChunkInfo]:
    """
    Split a video into overlapping chunks and extract representative frames.

    Args:
        video_path: Absolute path to the video file.
        chunk_size: Length of each chunk in seconds (default 7s — kept small for
                    fine-grained FAISS indexing; output windows are expanded to
                    MIN_RESULT_DURATION at query time).
        overlap: Overlap between consecutive chunks in seconds (default 3s).
        n_frames: Number of frames to sample per chunk (default 4).

    Returns:
        List of ChunkInfo objects, one per chunk.
    """
    if chunk_size <= 0 or not 0 <= overlap < chunk_size or n_frames <= 0:
        raise ValueError("Require chunk_size > overlap >= 0 and n_frames > 0")
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

        chunks.append(ChunkInfo(
            chunk_id=chunk_id,
            start_time=round(start, 3),
            end_time=round(end, 3),
        ))

        chunk_id += 1
        t += step

        # If the remaining segment is shorter than overlap, stop
        if end >= duration:
            break

    _extract_chunk_frames(video_path, chunks, n_frames, chunk_frame_dir)
    return chunks


def _extract_chunk_frames(
    video_path: str,
    chunks: List[ChunkInfo],
    n_frames: int,
    output_dir: Path,
) -> None:
    """Decode once in order, retaining H.264 reference frames between samples.

    Random seeks can lose reference frames in open-GOP videos. Overlapping
    chunks share a decode pass; only requested frames are converted/saved.
    """
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        requests = []
        for chunk in chunks:
            duration = chunk.end_time - chunk.start_time
            offsets = ([duration / 2] if n_frames == 1 else
                       [duration * (i + 1) / (n_frames + 1) for i in range(n_frames)])
            for i, offset in enumerate(offsets):
                requests.append((int((chunk.start_time + offset) * fps), chunk.chunk_id, i))
        requests.sort()
        frame_number = -1
        request_index = 0
        while request_index < len(requests):
            if not cap.grab():
                raise RuntimeError(
                    f"Video decoding stopped at frame {frame_number + 1}; "
                    f"{len(requests) - request_index} samples remain. "
                    "The video may be damaged or its duration inaccurate."
                )
            frame_number += 1
            if frame_number < requests[request_index][0]:
                continue
            ret, frame = cap.retrieve()
            if not ret:
                raise RuntimeError(f"Cannot decode sampled frame {frame_number}")
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            while request_index < len(requests) and requests[request_index][0] == frame_number:
                _, chunk_id, sample_id = requests[request_index]
                out_path = output_dir / f"chunk{chunk_id:04d}_frame{sample_id}.jpg"
                image.save(str(out_path), quality=90)
                chunks[chunk_id].frame_paths.append(str(out_path))
                request_index += 1
    finally:
        cap.release()


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
