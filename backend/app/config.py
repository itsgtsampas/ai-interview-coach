"""Typed application settings, loaded from environment / .env (12-Factor, principle III)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Interview Coach"
    app_version: str = "1.0.0"

    # Security
    secret_key: str = "dev-only-insecure-secret-change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Storage
    database_url: str = "sqlite:///./data/cvcoach.db"
    storage_dir: Path = Path("./data/storage")
    chroma_dir: Path = Path("./data/chroma")

    # LLM / embeddings.  "stub" needs no API key and no network.
    llm_provider: str = "stub"
    embedding_provider: str = "stub"
    openai_api_key: str | None = None
    openai_chat_model_large: str = "gpt-4o"
    openai_chat_model_small: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384

    # Uploads
    max_upload_bytes: int = 5 * 1024 * 1024
    max_pdf_pages: int = 20
    # A text PDF yields far more than this per page; below it, assume a scan.
    min_chars_per_page: int = 150

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(
                parents=True, exist_ok=True
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
