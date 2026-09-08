from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class SessionStatus(str, Enum):
    created = "created"
    ingesting = "ingesting"
    ready = "ready"
    analysed = "analysed"
    in_progress = "in_progress"
    completed = "completed"


class InterviewSession(SQLModel, table=True):
    __tablename__ = "interview_session"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=160)
    target_role: str = Field(default="", max_length=160)
    status: SessionStatus = Field(default=SessionStatus.created)
    created_at: datetime = Field(default_factory=utcnow)
