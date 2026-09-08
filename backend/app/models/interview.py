import json
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class QuestionCategory(str, Enum):
    technical = "technical"
    behavioural = "behavioural"


class Question(SQLModel, table=True):
    __tablename__ = "question"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_session.id", index=True)
    category: QuestionCategory
    text: str
    rationale: str = ""
    difficulty: int = Field(default=3, ge=1, le=5)
    linked_match_item_id: int | None = Field(default=None, foreign_key="match_item.id")
    linked_requirement: str = ""
    order_index: int = 0
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Answer(SQLModel, table=True):
    __tablename__ = "answer"

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    text: str
    duration_seconds: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluation"

    id: int | None = Field(default=None, primary_key=True)
    answer_id: int = Field(foreign_key="answer.id", index=True, unique=True)
    rubric: str = "technical"
    criterion_scores_json: str = "{}"
    overall_score: float = 0.0
    reasoning: str = ""
    strengths_json: str = "[]"
    improvements_json: str = "[]"
    model_answer: str = ""
    follow_up_question: str = ""
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def criterion_scores(self) -> dict[str, float]:
        return json.loads(self.criterion_scores_json)

    @property
    def strengths(self) -> list[str]:
        return json.loads(self.strengths_json)

    @property
    def improvements(self) -> list[str]:
        return json.loads(self.improvements_json)


class Scorecard(SQLModel, table=True):
    __tablename__ = "scorecard"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_session.id", index=True, unique=True)
    readiness_score: int = 0
    readiness_band: str = ""
    summary: str = ""
    competencies_json: str = "{}"
    strengths_json: str = "[]"
    gaps_json: str = "[]"
    action_items_json: str = "[]"
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)
