"""Stage 4: aggregate the session into a readiness scorecard.

Consumes only the stored outputs of stages 1-3 — it never re-reads the CV, so
every number on the scorecard traces back to a row in the database.
"""

import json

from sqlmodel import Session, select

from app.config import get_settings
from app.exceptions import StageNotReady
from app.llm.contracts import ScorecardOut
from app.llm.structured import complete_structured
from app.models import InterviewSession, Scorecard, SessionStatus
from app.prompts import build_scorecard
from app.services.analysis import get_report
from app.services.evaluation import evaluations_for_session

MIN_ANSWERS = 1


def build(session: InterviewSession, db: Session) -> Scorecard:
    settings = get_settings()
    report, items = get_report(session.id or 0, db)
    if report is None:
        raise StageNotReady("Run the match analysis before building a scorecard.")

    rows = evaluations_for_session(session.id or 0, db)
    if len(rows) < MIN_ANSWERS:
        raise StageNotReady(
            f"Answer and score at least {MIN_ANSWERS} question before building a scorecard."
        )

    report_payload = {
        "overall_score": report.overall_score,
        "verdict": report.verdict,
        "items": [
            {
                "requirement": i.requirement,
                "category": i.category.value if hasattr(i.category, "value") else str(i.category),
                "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            }
            for i in items
        ],
    }
    eval_payload = [
        {
            "question": q.text,
            "category": q.category.value,
            "overall_score": e.overall_score,
            "criterion_scores": e.criterion_scores,
        }
        for q, _a, e in rows
    ]

    out = complete_structured(
        build_scorecard.render(report_payload, eval_payload),
        ScorecardOut,
        db=db,
        session_id=session.id,
        model=settings.openai_chat_model_large,
        temperature=0.3,
    )

    existing = db.exec(select(Scorecard).where(Scorecard.session_id == session.id)).first()
    if existing:
        db.delete(existing)
        db.commit()

    card = Scorecard(
        session_id=session.id or 0,
        readiness_score=out.readiness_score,
        readiness_band=out.readiness_band,
        summary=out.summary,
        competencies_json=json.dumps(out.competencies),
        strengths_json=json.dumps(out.strengths),
        gaps_json=json.dumps(out.gaps),
        action_items_json=json.dumps([a.model_dump() for a in out.action_items]),
        prompt_version=build_scorecard.VERSION,
    )
    db.add(card)
    session.status = SessionStatus.completed
    db.add(session)
    db.commit()
    db.refresh(card)
    return card


def get_scorecard(session_id: int, db: Session) -> Scorecard | None:
    return db.exec(select(Scorecard).where(Scorecard.session_id == session_id)).first()
