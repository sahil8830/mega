"""
OCR Service - PaddleOCR (primary) with graceful fallback.

Smart App Control is disabled, so PaddleOCR DLLs are no longer blocked.
Uses the new PaddleOCR API (paddlex-based, v3+).

If PaddleOCR fails for any reason, OCR is gracefully disabled so the
rest of the indexing pipeline continues on visual + speech modalities.
"""
from typing import List

from app.config import get_settings

settings = get_settings()

_OCR_INSTANCE = None   # PaddleOCR instance or False (disabled)
_OCR_READY = False


def get_ocr_engine():
    """
    Lazy-initialize PaddleOCR on first call.
    Returns the OCR instance, or None if unavailable.
    """
    global _OCR_INSTANCE, _OCR_READY

    if _OCR_READY:
        return _OCR_INSTANCE if _OCR_INSTANCE else None

    _OCR_READY = True
    try:
        from paddleocr import PaddleOCR
        print("[OCR] Initializing PaddleOCR engine...")
        # New API (PaddleOCR v3+ / paddlex-based):
        # - use_textline_orientation replaces use_angle_cls
        # - no use_gpu param (auto-detected from device)
        ocr = PaddleOCR(
            use_textline_orientation=True,
            lang="en",
        )
        _OCR_INSTANCE = ocr
        print("[OCR] PaddleOCR ready.")
        return ocr
    except Exception as e:
        print(f"[OCR] WARNING: PaddleOCR unavailable ({type(e).__name__}: {e})")
        print("[OCR] OCR modality disabled - pipeline continues with visual + speech only.")
        _OCR_INSTANCE = None
        return None


def extract_text_from_frame(image_path: str) -> str:
    """
    Run PaddleOCR on a single frame image and return detected text.
    Returns empty string if OCR is disabled or image is unreadable.
    """
    ocr = get_ocr_engine()
    if ocr is None:
        return ""

    try:
        result = ocr.ocr(image_path)
        if not result or result[0] is None:
            return ""

        lines: List[str] = []
        for item in result[0]:
            # New API result format: {'transcription': text, 'score': conf, ...}
            if isinstance(item, dict):
                text = item.get("transcription", "") or item.get("text", "")
                score = item.get("score", 1.0)
                if score > 0.5 and text.strip():
                    lines.append(text.strip())
            # Old API format: [[bbox], (text, confidence)]
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                text_info = item[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    text, confidence = text_info[0], text_info[1]
                    if confidence > 0.5 and str(text).strip():
                        lines.append(str(text).strip())

        return " ".join(lines)

    except Exception as e:
        print(f"[OCR] Warning: OCR failed for {image_path}: {e}")
        return ""


def extract_text_from_chunk(frame_paths: List[str]) -> str:
    """
    Extract and concatenate OCR text from all frames in a chunk.
    Returns empty string if OCR is disabled or no text found.
    """
    if get_ocr_engine() is None:
        return ""

    all_text: List[str] = []
    for path in frame_paths:
        text = extract_text_from_frame(path)
        if text:
            all_text.append(text)

    # Deduplicate identical lines (same slide shown in multiple frames)
    seen = set()
    unique_text: List[str] = []
    for t in all_text:
        if t not in seen:
            seen.add(t)
            unique_text.append(t)

    return " ".join(unique_text)
