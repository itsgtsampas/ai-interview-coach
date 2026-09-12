from datetime import datetime

from pydantic import BaseModel, Field


class SuggestionOut(BaseModel):
    id: int
    match_item_id: int
    requirement: str
    bullet: str
    premise: str
    why: str
    if_you_cannot: str
    placeholders: list[str]
    prompt_version: str


class CoverLetterRequest(BaseModel):
    tone: str = Field(default="plain", pattern="^(plain|warm|formal)$")


class CoverLetterOut(BaseModel):
    id: int
    session_id: int
    tone: str
    subject: str
    body: str
    claims_used: list[str]
    prompt_version: str
    created_at: datetime
