"""
PaddleOCR Service.

Extracts on-screen text from video frames.
Engine is cached after first initialization (slow cold start).
"""
from functools import lru_cache
from typing import List

from app.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_ocr_engine():
    """
    Lazy-load and cache the PaddleOCR engine.

    use_angle_cls=True: handles rotated text
    lang='en': English; change to 'ch' for Chinese, etc.
    show_log=False: suppress verbose paddle output
    """
    print("[OCR] Initializing PaddleOCR engine...")
    # Import here to avoid slow import at module level
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(
        use_angle_cls=True,
        lang="en",
        show_log=False,
        use_gpu=(settings.device == "cuda"),
    )
    print("[OCR] PaddleOCR ready.")
    return ocr


def extract_text_from_frame(image_path: str) -> str:
    """
    Run PaddleOCR on a single frame image and return detected text.

    Returns empty string if no text is found or if image is unreadable.
    """
    ocr = get_ocr_engine()

    try:
        result = ocr.ocr(image_path, cls=True)
    except Exception as e:
        print(f"[OCR] Warning: OCR failed for {image_path}: {e}")
        return ""

    if not result or result[0] is None:
        return ""

    lines: List[str] = []
    for line in result[0]:
        # line format: [[bbox], (text, confidence)]
        if line and len(line) >= 2:
            text, confidence = line[1]
            if confidence > 0.5 and text.strip():
                lines.append(text.strip())

    return " ".join(lines)


def extract_text_from_chunk(frame_paths: List[str]) -> str:
    """
    Extract and concatenate OCR text from all frames in a chunk.

    Returns empty string if no text is found across all frames.
    """
    all_text: List[str] = []
    for path in frame_paths:
        text = extract_text_from_frame(path)
        if text:
            all_text.append(text)

    # Deduplicate identical lines (e.g., same slide shown in multiple frames)
    seen = set()
    unique_text: List[str] = []
    for t in all_text:
        if t not in seen:
            seen.add(t)
            unique_text.append(t)

    return " ".join(unique_text)
