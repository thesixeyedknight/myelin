from __future__ import annotations
import os
from pydantic import BaseModel


class Settings(BaseModel):
    # SDK reads GEMINI_API_KEY or GOOGLE_API_KEY automatically
    gemini_api_key: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # NCBI
    ncbi_email: str = os.getenv("NCBI_EMAIL", "")
    ncbi_api_key: str | None = os.getenv("NCBI_API_KEY")

    # Sandbox limits
    max_worker_seconds: int = int(os.getenv("MAX_WORKER_SECONDS", 10))
    max_worker_memory_mb: int = int(os.getenv("MAX_WORKER_MEMORY_MB", 256))


SETTINGS = Settings()
