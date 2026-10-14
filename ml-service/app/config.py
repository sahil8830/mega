from pydantic_settings import BaseSettings
from functools import lru_cache
import os
import platform
from importlib.util import find_spec
from pydantic import Field, model_validator


class Settings(BaseSettings):
    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    debug: bool = True

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017/mega"

    # Storage
    video_storage_path: str = "../backend/storage/videos"
    faiss_index_path: str = "./faiss"

    # CLIP
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"

    # Whisper
    whisper_model_size: str = "base"
    whisper_mlx_model: str = ""  # Optional local model path or Hugging Face repo

    # Optional ONNX text detector. Preprocessing and recognition remain PaddleOCR.
    ocr_detector_onnx_dir: str = ""
    ocr_exact_cache_mb: int = Field(16, ge=0)
    release_whisper_after_transcription: bool = True

    # Indexing: batch model calls without reducing temporal/frame sampling.
    chunk_size_seconds: int = Field(7, gt=0)
    chunk_overlap_seconds: int = Field(3, ge=0)
    frames_per_chunk: int = Field(4, gt=0)
    indexing_batch_size: int = Field(8, gt=0)
    clip_batch_size: int = Field(32, gt=0)

    @model_validator(mode="after")
    def validate_overlap(self):
        if self.chunk_overlap_seconds >= self.chunk_size_seconds:
            raise ValueError("CHUNK_OVERLAP_SECONDS must be less than CHUNK_SIZE_SECONDS")
        return self

    # Query expansion
    query_expansion_mode: str = "local"  # "local" | "openai"
    openai_api_key: str = ""

    # GPU
    force_cpu: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def device(self) -> str:
        """Prefer NVIDIA CUDA, then Apple MPS, otherwise CPU."""
        import torch  # lazy import — avoids slow torch init at config load time
        if self.force_cpu:
            return "cpu"
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    @property
    def whisper_device(self) -> str:
        """Keep Whisper on CPU for MPS (its sparse tensors are unsupported)."""
        return "cuda" if self.device == "cuda" else "cpu"

    @property
    def whisper_backend(self) -> str:
        if (not self.force_cpu and platform.system() == "Darwin"
                and platform.machine() == "arm64" and self.device == "mps"
                and find_spec("mlx_whisper") is not None):
            return "mlx"
        return "pytorch"



@lru_cache()
def get_settings() -> Settings:
    return Settings()
