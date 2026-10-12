"""
OCR Service - PaddleOCR (primary) with graceful fallback.

Smart App Control is disabled, so PaddleOCR DLLs are no longer blocked.
Uses the new PaddleOCR API (paddlex-based, v3+).

If PaddleOCR fails for any reason, OCR is gracefully disabled so the
rest of the indexing pipeline continues on visual + speech modalities.

The "ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute
<pir::DoubleAttribute>]" warning from PaddlePaddle's oneDNN backend is
a known Windows compatibility warning and is suppressed / treated as non-fatal.
"""
import os
# ── Suppress PaddlePaddle oneDNN/PIR warnings BEFORE any paddle import ─────────
# 'ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute]' is a
# known Windows compatibility warning from PaddlePaddle's oneDNN backend.
os.environ["FLAGS_use_mkldnn"]      = "0"   # disable oneDNN completely
os.environ["GLOG_minloglevel"]      = "3"   # suppress C++ INFO+WARNING logs
os.environ["PADDLE_CPP_LOG_LEVEL"] = "ERROR"
os.environ["FLAGS_pir_apply_shape_optimization_pass"] = "0"
import sys
import warnings
from typing import List

from app.config import get_settings

settings = get_settings()

# Suppress PaddlePaddle oneDNN verbose warnings on Windows
os.environ.setdefault("GLOG_minloglevel", "3")          # suppress C++ INFO/WARNING
os.environ.setdefault("FLAGS_use_mkldnn", "0")           # disable oneDNN (avoids the pir attr error)
os.environ.setdefault("PADDLE_CPP_LOG_LEVEL", "ERROR")

_OCR_INSTANCE = None   # PaddleOCR instance or False (disabled)
_OCR_READY = False
_OCR_DETECTOR_BACKEND = "paddle"


def get_ocr_engine():
    """
    Lazy-initialize PaddleOCR on first call.
    Returns the OCR instance, or None if unavailable.
    """
    global _OCR_INSTANCE, _OCR_READY, _OCR_DETECTOR_BACKEND

    if _OCR_READY:
        return _OCR_INSTANCE if _OCR_INSTANCE else None

    _OCR_READY = True
    try:
        from paddleocr import PaddleOCR
        print("[OCR] Initializing PaddleOCR engine...")

        # Redirect stderr briefly to suppress the oneDNN pir::ArrayAttribute warning
        import io
        _old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            ocr = PaddleOCR(
                use_textline_orientation=True,
                lang="en",
            )
        finally:
            # Restore stderr (optionally print suppressed content at DEBUG level)
            captured = sys.stderr.getvalue()
            sys.stderr = _old_stderr
            if captured and "ConvertPirAttribute2RuntimeAttribute" not in captured:
                sys.stderr.write(captured)

        _OCR_INSTANCE = ocr
        print("[OCR] PaddleOCR ready.")
        if settings.ocr_detector_onnx_dir:
            from app.services.ocr_acceleration import accelerate_detector
            _OCR_DETECTOR_BACKEND = accelerate_detector(
                ocr,
                settings.ocr_detector_onnx_dir,
                force_cpu=settings.force_cpu,
            )
        else:
            _OCR_DETECTOR_BACKEND = "paddle"
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
    The oneDNN 'ConvertPirAttribute2RuntimeAttribute' warning is suppressed
    as it is a known PaddlePaddle Windows compatibility issue, not a real error.
    """
    ocr = get_ocr_engine()
    if ocr is None:
        return ""

    try:
        # Suppress the per-frame oneDNN stderr noise
        import io
        _old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = list(ocr.predict(image_path))
        finally:
            captured = sys.stderr.getvalue()
            sys.stderr = _old_stderr
            # Only forward non-PaddlePaddle-oneDNN warnings
            if captured and "ConvertPirAttribute2RuntimeAttribute" not in captured \
                         and "pir::ArrayAttribute" not in captured:
                sys.stderr.write(captured)

        return _parse_ocr_results(result)

    except Exception as e:
        # Report failures; indexing continues with visual + speech modalities.
        print(f"[OCR] Frame failed ({type(e).__name__}: {e})")
        return ""


def _parse_ocr_results(results) -> str:
    """Read PaddleOCR 3.x text arrays, preserving confidence filtering."""
    lines = []
    for result in results:
        if result is None:
            continue
        for text, score in zip(result.get("rec_texts", []), result.get("rec_scores", [])):
            if float(score) > 0.5 and text.strip():
                lines.append(text.strip())
    return " ".join(lines)


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
