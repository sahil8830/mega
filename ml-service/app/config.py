from pydantic_settings import BaseSettings
from functools import lru_cache
import os


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
        """Returns 'cuda' if a GPU is available and FORCE_CPU is not set, else 'cpu'."""
        import torch  # lazy import — avoids slow torch init at config load time
        if self.force_cpu:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"



@lru_cache()
def get_settings() -> Settings:
    return Settings()
