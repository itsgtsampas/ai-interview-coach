"""Pydantic contracts for every structured LLM output.

These are the *only* shapes the application accepts back from a model.  They are
converted to a JSON schema for providers that support strict structured output,
and they are the validation target for every response regardless of provider.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# --- Stage 1: requirement extraction --------------------------------------
class RequirementOut(BaseModel):
    text: str = Field(min_length=3, max_length=300)
    category: Literal["must_have", "nice_to_have"] = "must_have"
    kind: Literal["evidenceable", "behavioural"] = "evidenceable"


class RequirementsOut(BaseModel):
    # May legitimately be empty: a page with no requirements section yields
    # nothing, and that must be representable rather than fabricated.
    requirements: list[RequirementOut] = Field(max_length=20)


# --- Stage 2: match analysis ----------------------------------------------
class MatchItemOut(BaseModel):
    requirement: str
    category: Literal["must_have", "nice_to_have"] = "must_have"
    kind: Literal["evidenceable", "behavioural"] = "evidenceable"
    status: Literal["strong", "partial", "missing"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    evidence_quote: str | None = None
    evidence_page: int | None = None
    evidence_chunk_id: str | None = None
    evidence_section: str | None = None


class MatchReportOut(BaseModel):
    overall_score: int = Field(ge=0, le=100)

    # Weighted averages come back fractional as often as not; rounding here
    # saves a repair round trip and keeps the stored contract an integer.
    @field_validator("overall_score", mode="before")
    @classmethod
    def _round_score(cls, v):
        return round(v) if isinstance(v, float) else v
    verdict: str
    summary: str
    items: list[MatchItemOut]


# --- Stage 3: question generation -----------------------------------------
class QuestionOut(BaseModel):
    category: Literal["technical", "behavioural"]
    text: str = Field(min_length=10)
    rationale: str = ""
    difficulty: int = Field(ge=1, le=5, default=3)
    linked_requirement: str = ""


class QuestionsOut(BaseModel):
    questions: list[QuestionOut] = Field(min_length=1, max_length=20)


# --- Stage 4: answer evaluation -------------------------------------------
class CriterionScore(BaseModel):
    name: str
    score: int = Field(ge=1, le=5)
    comment: str = ""


class EvaluationOut(BaseModel):
    rubric: Literal["star", "technical"]
    reasoning: str = Field(description="Step-by-step analysis, written before scoring.")
    criteria: list[CriterionScore] = Field(min_length=3)
    overall_score: float = Field(ge=1.0, le=5.0)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    model_answer: str = ""
    follow_up_question: str = ""


# --- Stage 5: scorecard ----------------------------------------------------
class ActionItem(BaseModel):
    priority: Literal["high", "medium", "low"]
    title: str
    why: str = ""
    how: str = ""


class ScorecardOut(BaseModel):
    readiness_score: int = Field(ge=0, le=100)

    @field_validator("readiness_score", mode="before")
    @classmethod
    def _round_score(cls, v):
        return round(v) if isinstance(v, float) else v
    readiness_band: str
    summary: str
    competencies: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class RewriteOut(BaseModel):
    """A CV bullet *shape*, not a claim.

    `placeholders` is validated separately by the service: a bullet that came
    back with no placeholders and no supporting evidence is the fabrication case
    this stage exists to prevent.
    """

    bullet: str = Field(min_length=10, max_length=400)
    premise: str = ""
    why: str = ""
    if_you_cannot: str = ""
    placeholders: list[str] = Field(default_factory=list)


class CoverLetterOut(BaseModel):
    subject: str = ""
    body: str = Field(min_length=80)
    claims_used: list[str] = Field(default_factory=list)
