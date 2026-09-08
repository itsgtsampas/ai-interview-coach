from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlmodel import select

from app.agents.coach import ask
from app.dependencies import CurrentUser, OwnedSession, SessionDep
from app.exceptions import NotFound
from app.models import Answer, Evaluation, InterviewSession, Question
from app.schemas.interview import (
    ActionItemOut,
    AnswerCreate,
    AnswerOut,
    CoachRequest,
    CoachResponse,
    CoachStepOut,
    CriterionOut,
    EvaluationOut,
    QuestionOut,
    ScorecardOut,
)
from app.services.evaluation import evaluate
from app.services.questions import generate, list_questions
from app.services.scorecard import build, get_scorecard

router = APIRouter(prefix="/api/v1", tags=["interview"])


def _question_out(q: Question, db) -> QuestionOut:
    answered = db.exec(select(Answer).where(Answer.question_id == q.id)).first() is not None
    return QuestionOut(
        id=q.id or 0,
        category=q.category,
        text=q.text,
        rationale=q.rationale,
        difficulty=q.difficulty,
        linked_requirement=q.linked_requirement,
        order_index=q.order_index,
        answered=answered,
    )


def _evaluation_out(e: Evaluation) -> EvaluationOut:
    return EvaluationOut(
        id=e.id or 0,
        answer_id=e.answer_id,
        rubric=e.rubric,
        overall_score=e.overall_score,
        reasoning=e.reasoning,
        criteria=[CriterionOut(name=k, score=v) for k, v in e.criterion_scores.items()],
        strengths=e.strengths,
        improvements=e.improvements,
        model_answer=e.model_answer,
        follow_up_question=e.follow_up_question,
        prompt_version=e.prompt_version,
    )


@router.post("/sessions/{session_id}/questions", response_model=list[QuestionOut],
             status_code=status.HTTP_201_CREATED)
def create_questions(
    sess: OwnedSession,
    db: SessionDep,
    technical: Annotated[int, Query(ge=1, le=10)] = 5,
    behavioural: Annotated[int, Query(ge=0, le=10)] = 3,
) -> list[QuestionOut]:
    questions = generate(sess, db, n_technical=technical, n_behavioural=behavioural)
    return [_question_out(q, db) for q in questions]


@router.get("/sessions/{session_id}/questions", response_model=list[QuestionOut])
def read_questions(sess: OwnedSession, db: SessionDep) -> list[QuestionOut]:
    return [_question_out(q, db) for q in list_questions(sess.id or 0, db)]


@router.post("/questions/{question_id}/answers", response_model=AnswerOut,
             status_code=status.HTTP_201_CREATED)
def submit_answer(
    question_id: int, body: AnswerCreate, user: CurrentUser, db: SessionDep
) -> AnswerOut:
    question = db.get(Question, question_id)
    if question is None:
        raise NotFound("Question not found.")
    sess = db.get(InterviewSession, question.session_id)
    if sess is None or sess.user_id != user.id:
        raise NotFound("Question not found.")

    answer = Answer(
        question_id=question_id, text=body.text, duration_seconds=body.duration_seconds
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)

    evaluation = evaluate(answer, question, db, sess.id or 0)
    return AnswerOut(
        id=answer.id or 0,
        question_id=question_id,
        text=answer.text,
        duration_seconds=answer.duration_seconds,
        evaluation=_evaluation_out(evaluation),
    )


@router.get("/questions/{question_id}/answer", response_model=AnswerOut)
def read_answer(question_id: int, user: CurrentUser, db: SessionDep) -> AnswerOut:
    question = db.get(Question, question_id)
    if question is None:
        raise NotFound("Question not found.")
    sess = db.get(InterviewSession, question.session_id)
    if sess is None or sess.user_id != user.id:
        raise NotFound("Question not found.")
    answer = db.exec(
        select(Answer).where(Answer.question_id == question_id).order_by(Answer.id.desc())
    ).first()
    if answer is None:
        raise NotFound("This question has not been answered yet.")
    evaluation = db.exec(select(Evaluation).where(Evaluation.answer_id == answer.id)).first()
    return AnswerOut(
        id=answer.id or 0,
        question_id=question_id,
        text=answer.text,
        duration_seconds=answer.duration_seconds,
        evaluation=_evaluation_out(evaluation) if evaluation else None,
    )


def _scorecard_out(card) -> ScorecardOut:
    import json

    return ScorecardOut(
        id=card.id or 0,
        session_id=card.session_id,
        readiness_score=card.readiness_score,
        readiness_band=card.readiness_band,
        summary=card.summary,
        competencies=json.loads(card.competencies_json),
        strengths=json.loads(card.strengths_json),
        gaps=json.loads(card.gaps_json),
        action_items=[ActionItemOut(**a) for a in json.loads(card.action_items_json)],
    )


@router.post("/sessions/{session_id}/scorecard", response_model=ScorecardOut,
             status_code=status.HTTP_201_CREATED)
def create_scorecard(sess: OwnedSession, db: SessionDep) -> ScorecardOut:
    return _scorecard_out(build(sess, db))


@router.get("/sessions/{session_id}/scorecard", response_model=ScorecardOut)
def read_scorecard(sess: OwnedSession, db: SessionDep) -> ScorecardOut:
    card = get_scorecard(sess.id or 0, db)
    if card is None:
        raise NotFound("No scorecard has been built for this session yet.")
    return _scorecard_out(card)


@router.post("/sessions/{session_id}/coach", response_model=CoachResponse)
def coach(sess: OwnedSession, body: CoachRequest, db: SessionDep) -> CoachResponse:
    result = ask(body.message, user_id=sess.user_id, session_id=sess.id or 0, db=db)
    return CoachResponse(
        answer=result.answer,
        steps=[
            CoachStepOut(thought=s.thought, tool=s.tool, observation=s.observation)
            for s in result.steps
        ],
    )
