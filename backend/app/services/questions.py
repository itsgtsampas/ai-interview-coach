"""Stage 2: turn the gap analysis into personalised interview questions."""

import json

from sqlmodel import Session, delete, select

from app.config import get_settings
from app.exceptions import StageNotReady
from app.llm.contracts import QuestionsOut
from app.llm.structured import complete_structured
from app.models import InterviewSession, Question, QuestionCategory, SessionStatus
from app.prompts import generate_questions
from app.services.analysis import get_report


def generate(
    session: InterviewSession, db: Session, *, n_technical: int = 5, n_behavioural: int = 3
) -> list[Question]:
    settings = get_settings()
    report, items = get_report(session.id or 0, db)
    if report is None:
        raise StageNotReady("Run the match analysis before generating questions.")

    payload_items = [
        {
            "requirement": i.requirement,
            "category": i.category.value if hasattr(i.category, "value") else str(i.category),
            "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            "evidence_quote": i.evidence_quote,
        }
        for i in items
    ]

    out = complete_structured(
        generate_questions.render(
            payload_items, session.target_role, n_technical, n_behavioural
        ),
        QuestionsOut,
        db=db,
        session_id=session.id,
        # Higher temperature here on purpose: questions should not repeat across
        # sessions, whereas scoring must be reproducible.
        model=settings.openai_chat_model_large,
        temperature=0.8,
    )

    db.exec(delete(Question).where(Question.session_id == session.id))
    db.commit()

    by_requirement = {i.requirement: i.id for i in items}
    created: list[Question] = []
    for order, q in enumerate(out.questions):
        question = Question(
            session_id=session.id or 0,
            category=QuestionCategory(q.category),
            text=q.text,
            rationale=q.rationale,
            difficulty=q.difficulty,
            linked_requirement=q.linked_requirement,
            linked_match_item_id=by_requirement.get(q.linked_requirement),
            order_index=order,
            prompt_version=generate_questions.VERSION,
        )
        db.add(question)
        created.append(question)

    session.status = SessionStatus.in_progress
    db.add(session)
    db.commit()
    for q in created:
        db.refresh(q)
    return created


def list_questions(session_id: int, db: Session) -> list[Question]:
    return list(db.exec(
        select(Question).where(Question.session_id == session_id).order_by(Question.order_index)
    ).all())
