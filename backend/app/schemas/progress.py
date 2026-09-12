from datetime import datetime

from pydantic import BaseModel


class ProgressPoint(BaseModel):
    session_id: int
    title: str
    target_role: str
    created_at: datetime
    match_score: int | None
    readiness_score: int | None
    answers: int
    mean_answer_score: float | None


class RecurringGap(BaseModel):
    """One requirement that went unevidenced across more than one application."""

    requirement: str
    missing_in: int
    sessions: list[str]


class CompetencyTrend(BaseModel):
    name: str
    first: float
    latest: float
    delta: float
    points: list[float]


class ProgressOut(BaseModel):
    sessions_total: int
    sessions_scored: int
    answers_total: int
    mean_answer_score: float | None
    best_readiness: int | None
    latest_readiness: int | None
    readiness_delta: int | None
    mean_match: float | None
    # False when there are too few scored sessions for a line to mean anything;
    # the client shows figures instead of drawing a trend through two dots.
    has_trend: bool
    points: list[ProgressPoint]
    recurring_gaps: list[RecurringGap]
    competencies: list[CompetencyTrend]
