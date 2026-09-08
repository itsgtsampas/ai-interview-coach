from pydantic import BaseModel, Field

from app.models import QuestionCategory


class QuestionOut(BaseModel):
    id: int
    category: QuestionCategory
    text: str
    rationale: str
    difficulty: int
    linked_requirement: str
    order_index: int
    answered: bool = False


class AnswerCreate(BaseModel):
    text: str = Field(min_length=10, max_length=8000)
    duration_seconds: int = Field(default=0, ge=0, le=7200)


class CriterionOut(BaseModel):
    name: str
    score: float


class EvaluationOut(BaseModel):
    id: int
    answer_id: int
    rubric: str
    overall_score: float
    reasoning: str
    criteria: list[CriterionOut]
    strengths: list[str]
    improvements: list[str]
    model_answer: str
    follow_up_question: str
    prompt_version: str


class AnswerOut(BaseModel):
    id: int
    question_id: int
    text: str
    duration_seconds: int
    evaluation: EvaluationOut | None = None


class ActionItemOut(BaseModel):
    priority: str
    title: str
    why: str = ""
    how: str = ""


class ScorecardOut(BaseModel):
    id: int
    session_id: int
    readiness_score: int
    readiness_band: str
    summary: str
    competencies: dict[str, float]
    strengths: list[str]
    gaps: list[str]
    action_items: list[ActionItemOut]


class CoachRequest(BaseModel):
    message: str = Field(min_length=3, max_length=1000)


class CoachStepOut(BaseModel):
    thought: str
    tool: str | None = None
    observation: str | None = None


class CoachResponse(BaseModel):
    answer: str
    steps: list[CoachStepOut]
