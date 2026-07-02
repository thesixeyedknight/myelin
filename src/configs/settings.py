from __future__ import annotations
import os
import yaml
from pathlib import Path
from pydantic import BaseModel



class Settings(BaseModel):
    model_config = {"protected_namespaces": ()}  # Allow model_ prefix
    
    # SDK reads GEMINI_API_KEY or GOOGLE_API_KEY automatically
    gemini_api_key: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # NCBI
    ncbi_email: str = os.getenv("NCBI_EMAIL", "")
    ncbi_api_key: str | None = os.getenv("NCBI_API_KEY")

    # Model tiers for cascading fallback (using available free tier models)
    model_pro: str = os.getenv("MODEL_PRO", "gemini-2.5-pro")
    model_flash: str = os.getenv("MODEL_FLASH", "gemini-2.5-flash")
    model_lite: str = os.getenv("MODEL_LITE", "gemini-2.5-flash-lite")
    
    # Daily quotas (requests per day)
    quota_pro: int = int(os.getenv("QUOTA_PRO", 50))
    quota_flash: int = int(os.getenv("QUOTA_FLASH", 250))
    quota_lite: int = int(os.getenv("QUOTA_LITE", 1000))

    # Sandbox limits
    max_worker_seconds: int = int(os.getenv("MAX_WORKER_SECONDS", 10))
    max_worker_memory_mb: int = int(os.getenv("MAX_WORKER_MEMORY_MB", 256))

    # LLM IO dump - save full prompts/responses under logs/llm/ for debugging
    save_llm_io: bool = os.getenv("SAVE_LLM_IO", "0") in {"1", "true", "True"}

    # RAG settings
    rag_enabled: bool = os.getenv("RAG_ENABLED", "true").lower() == "true"
    rag_collection_name: str = os.getenv("RAG_COLLECTION_NAME", "myelin_kb")
    rag_chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", 500))
    rag_chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", 100))
    rag_max_file_size_mb: int = int(os.getenv("RAG_MAX_FILE_SIZE_MB", 10))
    rag_relevance_threshold: float = float(os.getenv("RAG_RELEVANCE_THRESHOLD", 0.3))

    # Local LLM settings
    llm_backend: str = os.getenv("LLM_BACKEND", "ollama")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "llama3")

    @classmethod
    def load(cls) -> Settings:
        # Load from config.yaml if exists
        config_path = Path("config.yaml")
        file_data = {}
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    file_data = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Failed to load config.yaml: {e}")
        
        # Helper to get value from source
        def get(key, default):
            return os.getenv(key.upper(), file_data.get(key, default))

        def get_bool(key, default: bool) -> bool:
            # config.yaml (YAML) may hand back a native bool; env vars are
            # always strings. Handle both instead of assuming .lower() exists.
            val = get(key, default)
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in {"1", "true", "yes"}

        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or file_data.get("gemini_api_key", ""),
            gemini_model=get("gemini_model", "gemini-2.5-flash"),
            log_level=get("log_level", "INFO"),
            ncbi_email=get("ncbi_email", ""),
            ncbi_api_key=get("ncbi_api_key", None),
            model_pro=get("model_pro", "gemini-2.5-pro"),
            model_flash=get("model_flash", "gemini-2.5-flash"),
            model_lite=get("model_lite", "gemini-2.5-flash-lite"),
            quota_pro=int(get("quota_pro", 50)),
            quota_flash=int(get("quota_flash", 250)),
            quota_lite=int(get("quota_lite", 1000)),
            max_worker_seconds=int(get("max_worker_seconds", 10)),
            max_worker_memory_mb=int(get("max_worker_memory_mb", 256)),
            save_llm_io=get_bool("save_llm_io", False),
            rag_enabled=get_bool("rag_enabled", True),
            rag_collection_name=get("rag_collection_name", "myelin_kb"),
            rag_chunk_size=int(get("rag_chunk_size", 500)),
            rag_chunk_overlap=int(get("rag_chunk_overlap", 100)),
            rag_max_file_size_mb=int(get("rag_max_file_size_mb", 10)),
            rag_relevance_threshold=float(get("rag_relevance_threshold", 0.3)),
            llm_backend=get("llm_backend", "ollama"),
            llm_model_name=get("llm_model_name", "llama3"),
        )


SETTINGS = Settings.load()
LLM_BACKEND = SETTINGS.llm_backend
MODEL_NAME = SETTINGS.llm_model_name
