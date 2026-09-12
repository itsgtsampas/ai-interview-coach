from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class RequirementCategory(str, Enum):
    must_have = "must_have"
    nice_to_have = "nice_to_have"


class RequirementKind(str, Enum):
    """Whether a CV is capable of evidencing this requirement at all.

    "Excellent communication skills" cannot be shown by any CV, so counting it
    as missing penalises the candidate for a limitation of the medium. Those
    requirements are assessed in the interview instead, and are excluded from
    the match score.
    """

    evidenceable = "evidenceable"
    behavioural = "behavioural"


class EvidenceStatus(str, Enum):
    strong = "strong"
    partial = "partial"
    missing = "missing"


class MatchReport(SQLModel, table=True):
    __tablename__ = "match_report"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_session.id", index=True, unique=True)
    overall_score: int = 0
    verdict: str = ""
    summary: str = ""
    prompt_version: str = ""
    model: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class MatchItem(SQLModel, table=True):
    __tablename__ = "match_item"

    id: int | None = Field(default=None, primary_key=True)
    report_id: int = Field(foreign_key="match_report.id", index=True)
    requirement: str
    category: RequirementCategory = RequirementCategory.must_have
    kind: RequirementKind = RequirementKind.evidenceable
    status: EvidenceStatus = EvidenceStatus.missing
    confidence: float = 0.0
    evidence_quote: str | None = None
    evidence_page: int | None = None
    evidence_chunk_id: str | None = None
    evidence_section: str | None = None
    reasoning: str = ""
    order_index: int = 0
