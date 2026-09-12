"""Derived writing: bullet rewrites and cover letters.

Both are cached per source row rather than regenerated on every view. A rewrite
belongs to one match item, a letter to one session, and both are deleted with
their parent because both quote the CV.
"""

import json
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class CvSuggestion(SQLModel, table=True):
    __tablename__ = "cv_suggestion"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_session.id", index=True)
    match_item_id: int = Field(foreign_key="match_item.id", index=True, unique=True)
    requirement: str = ""
    bullet: str = ""
    premise: str = ""
    why: str = ""
    if_you_cannot: str = ""
    placeholders_json: str = "[]"
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def placeholders(self) -> list[str]:
        return json.loads(self.placeholders_json)


class CoverLetter(SQLModel, table=True):
    __tablename__ = "cover_letter"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_session.id", index=True, unique=True)
    tone: str = "plain"
    subject: str = ""
    body: str = ""
    claims_used_json: str = "[]"
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def claims_used(self) -> list[str]:
        return json.loads(self.claims_used_json)
