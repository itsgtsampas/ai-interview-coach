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

    # The application talks to the OpenAI API. "stub" selects the deterministic
    # test double in app/llm/stub.py — it exists so the test suite and the eval
    # harness can run free and reproducibly, and it is not a supported way to
    # run the product.
    llm_provider: str = "openai"
    embedding_provider: str = "stub"
    openai_api_key: str | None = None
    # Both tiers default to the cheap model. The two-tier split is real — see
    # the services — but defaulting LARGE to gpt-4o meant forgetting one line in
    # .env silently ran almost the whole application at ~17x the price. Opting
    # into the expensive model should be deliberate.
    openai_chat_model_large: str = "gpt-4o-mini"
    openai_chat_model_small: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384

    # Hard ceiling on cumulative spend, in USD, across the whole database.
    # The rate limiter caps requests per caller; this caps money. A retry loop,
    # a runaway eval sweep or a forgotten browser tab cannot exceed it, because
    # every call checks the running total before it reaches a provider.
    # 0 disables the check. Ignored entirely by the stub, which is free.
    max_spend_usd: float = 5.0

    # Uploads
    max_upload_bytes: int = 5 * 1024 * 1024
    max_pdf_pages: int = 20
    # A text PDF yields far more than this per page; below it, assume a scan.
    min_chars_per_page: int = 150

    # Demo aid, off by default. The stub answers in about five milliseconds, so
    # a stream finishes before the browser paints a frame and the streaming UI
    # is never seen. Setting this pauses between chunks so the transport can be
    # demonstrated without a provider key. It is NOT product behaviour: it adds
    # latency that does not exist, and it stays 0 everywhere but a demo.
    stub_stream_delay_ms: int = 0

    # Rate limiting. Ceilings live in app/ratelimit.py; this only switches the
    # whole mechanism off, which the test suite needs and nothing else should.
    disable_rate_limits: bool = False

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
