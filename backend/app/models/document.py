from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class DocumentKind(str, Enum):
    cv = "cv"
    jd = "jd"


class IngestStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_session.id", index=True)
    kind: DocumentKind
    original_filename: str = Field(max_length=255)
    sha256: str = Field(max_length=64, index=True)
    size_bytes: int
    page_count: int = 0
    char_count: int = 0
    storage_path: str = ""
    ingest_status: IngestStatus = Field(default=IngestStatus.pending)
    ingest_error: str | None = None
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
