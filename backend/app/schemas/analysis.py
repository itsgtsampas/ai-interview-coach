from pydantic import BaseModel

from app.models.analysis import EvidenceStatus, RequirementCategory


class MatchItemOut(BaseModel):
    id: int
    requirement: str
    category: RequirementCategory
    status: EvidenceStatus
    confidence: float
    reasoning: str
    evidence_quote: str | None = None
    evidence_page: int | None = None
    evidence_section: str | None = None


class MatchReportOut(BaseModel):
    id: int
    session_id: int
    overall_score: int
    verdict: str
    summary: str
    prompt_version: str
    items: list[MatchItemOut]
    counts: dict[str, int]
