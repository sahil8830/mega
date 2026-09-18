from fastapi import APIRouter
import torch
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/ml/health", tags=["Health"])
async def health_check():
    """
    Liveness probe.
    Returns service status, device info, and CUDA availability.
    """
    return {
        "status": "ok",
        "device": settings.device,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "clip_model": settings.clip_model_name,
        "whisper_model": settings.whisper_model_size,
    }
