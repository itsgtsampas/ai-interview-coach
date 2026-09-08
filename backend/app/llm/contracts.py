"""Pydantic contracts for every structured LLM output.

These are the *only* shapes the application accepts back from a model.  They are
converted to a JSON schema for providers that support strict structured output,
and they are the validation target for every response regardless of provider.
"""

from typing import Literal

from pydantic import BaseModel, Field


# --- Stage 1: requirement extraction --------------------------------------
class RequirementOut(BaseModel):
    text: str = Field(min_length=3, max_length=300)
    category: Literal["must_have", "nice_to_have"] = "must_have"


class RequirementsOut(BaseModel):
    requirements: list[RequirementOut] = Field(min_length=1, max_length=20)


# --- Stage 2: match analysis ----------------------------------------------
class MatchItemOut(BaseModel):
    requirement: str
    category: Literal["must_have", "nice_to_have"] = "must_have"
    status: Literal["strong", "partial", "missing"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    evidence_quote: str | None = None
    evidence_page: int | None = None
    evidence_chunk_id: str | None = None
    evidence_section: str | None = None


class MatchReportOut(BaseModel):
    overall_score: int = Field(ge=0, le=100)
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
    readiness_band: str
    summary: str
    competencies: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
