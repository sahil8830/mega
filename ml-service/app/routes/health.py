from fastapi import APIRouter
import torch
from app.config import get_settings
from app.services.whisper_asr import active_whisper_backend
from app.services import ocr_service
from app.services.weighting_module import weighting_status

router = APIRouter()
settings = get_settings()


@router.get("/ml/health", tags=["Health"])
async def health_check():
    """
    Liveness probe.
    Returns service status and the devices selected for each model.
    """
    return {
        "status": "ok",
        "weighting_model": weighting_status(),
        "device": settings.device,
        "whisper_device": "metal" if active_whisper_backend() == "mlx" else settings.whisper_device,
        "whisper_backend": active_whisper_backend(),
        "mps_available": torch.backends.mps.is_available(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "clip_model": settings.clip_model_name,
        "whisper_model": settings.whisper_model_size,
        "ocr_ready": ocr_service._OCR_READY,
        "ocr_detector_backend": (
            ocr_service._OCR_DETECTOR_BACKEND if ocr_service._OCR_READY else None
        ),
        "ocr_detector_configured": bool(settings.ocr_detector_onnx_dir),
    }
