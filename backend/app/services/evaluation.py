"""Stage 3: score one answer against the rubric its question calls for."""

import json

from sqlmodel import Session, select

from app.config import get_settings
from app.llm.contracts import EvaluationOut
from app.llm.structured import complete_structured
from app.models import Answer, Evaluation, Question, QuestionCategory
from app.prompts import evaluate_answer


def evaluate(answer: Answer, question: Question, db: Session, session_id: int) -> Evaluation:
    settings = get_settings()
    rubric = "star" if question.category == QuestionCategory.behavioural else "technical"

    out = complete_structured(
        evaluate_answer.render(
            question=question.text,
            answer_text=answer.text,
            rubric=rubric,
            linked_requirement=question.linked_requirement,
        ),
        EvaluationOut,
        db=db,
        session_id=session_id,
        # Temperature 0: the same answer must always receive the same score.
        model=settings.openai_chat_model_large,
        temperature=0.0,
    )

    existing = db.exec(select(Evaluation).where(Evaluation.answer_id == answer.id)).first()
    if existing:
        db.delete(existing)
        db.commit()

    evaluation = Evaluation(
        answer_id=answer.id or 0,
        rubric=out.rubric,
        criterion_scores_json=json.dumps({c.name: c.score for c in out.criteria}),
        overall_score=out.overall_score,
        reasoning=out.reasoning,
        strengths_json=json.dumps(out.strengths),
        improvements_json=json.dumps(out.improvements),
        model_answer=out.model_answer,
        follow_up_question=out.follow_up_question,
        prompt_version=evaluate_answer.VERSION,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def evaluations_for_session(session_id: int, db: Session) -> list[tuple[Question, Answer, Evaluation]]:
    rows: list[tuple[Question, Answer, Evaluation]] = []
    questions = db.exec(select(Question).where(Question.session_id == session_id)).all()
    for q in questions:
        answer = db.exec(
            select(Answer).where(Answer.question_id == q.id).order_by(Answer.id.desc())
        ).first()
        if answer is None:
            continue
        ev = db.exec(select(Evaluation).where(Evaluation.answer_id == answer.id)).first()
        if ev is not None:
            rows.append((q, answer, ev))
    return rows
