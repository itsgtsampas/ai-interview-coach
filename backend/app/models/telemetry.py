from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class LLMCall(SQLModel, table=True):
    """One row per model invocation.

    Gives per-session cost, p95 latency per stage, cache hit rate, and lets any
    stored output be traced back to the exact prompt version that produced it.
    """

    __tablename__ = "llm_call"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int | None = Field(default=None, foreign_key="interview_session.id", index=True)
    stage: str = Field(index=True)
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cache_hit: bool = False
    status: str = "ok"
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
