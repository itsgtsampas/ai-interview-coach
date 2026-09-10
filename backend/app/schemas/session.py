from datetime import datetime

from pydantic import BaseModel, Field

from app.models import DocumentKind, DocumentSource, IngestStatus, SessionStatus


class SessionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    target_role: str = Field(default="", max_length=160)


class DocumentTextCreate(BaseModel):
    """A document supplied as pasted text rather than an uploaded file."""

    text: str = Field(min_length=1, max_length=200_000)
    title: str = Field(default="Pasted job description", max_length=160)


class DocumentOut(BaseModel):
    id: int
    kind: DocumentKind
    source: DocumentSource = DocumentSource.pdf
    original_filename: str
    ingest_status: IngestStatus
    ingest_error: str | None = None
    page_count: int
    char_count: int
    chunk_count: int


class SessionOut(BaseModel):
    id: int
    title: str
    target_role: str
    status: SessionStatus
    created_at: datetime
    documents: list[DocumentOut] = []
    has_analysis: bool = False
    question_count: int = 0
    answered_count: int = 0
    readiness_score: int | None = None
