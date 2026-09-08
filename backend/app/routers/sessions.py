from pathlib import Path

from fastapi import APIRouter, status
from sqlmodel import delete, select

from app.dependencies import CurrentUser, OwnedSession, PageDep, SessionDep
from app.models import (
    Answer,
    Document,
    Evaluation,
    InterviewSession,
    MatchItem,
    MatchReport,
    Question,
    Scorecard,
)
from app.rag import store
from app.schemas.session import DocumentOut, SessionCreate, SessionOut

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _to_out(sess: InterviewSession, db) -> SessionOut:
    docs = db.exec(select(Document).where(Document.session_id == sess.id)).all()
    report = db.exec(select(MatchReport).where(MatchReport.session_id == sess.id)).first()
    questions = db.exec(select(Question).where(Question.session_id == sess.id)).all()
    answered = 0
    for q in questions:
        if db.exec(select(Answer).where(Answer.question_id == q.id)).first():
            answered += 1
    card = db.exec(select(Scorecard).where(Scorecard.session_id == sess.id)).first()
    return SessionOut(
        id=sess.id or 0,
        title=sess.title,
        target_role=sess.target_role,
        status=sess.status,
        created_at=sess.created_at,
        documents=[DocumentOut.model_validate(d, from_attributes=True) for d in docs],
        has_analysis=report is not None,
        question_count=len(questions),
        answered_count=answered,
        readiness_score=card.readiness_score if card else None,
    )


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionCreate, user: CurrentUser, db: SessionDep) -> SessionOut:
    sess = InterviewSession(
        user_id=user.id or 0, title=body.title, target_role=body.target_role
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return _to_out(sess, db)


@router.get("", response_model=list[SessionOut])
def list_sessions(user: CurrentUser, db: SessionDep, page: PageDep) -> list[SessionOut]:
    rows = db.exec(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.id.desc())
        .offset(page.skip)
        .limit(page.limit)
    ).all()
    return [_to_out(s, db) for s in rows]


@router.get("/{session_id}", response_model=SessionOut)
def get_session_detail(sess: OwnedSession, db: SessionDep) -> SessionOut:
    return _to_out(sess, db)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(sess: OwnedSession, db: SessionDep) -> None:
    """Full erasure: rows, vectors and the uploaded files.

    A CV is personal data, so 'delete' has to mean delete everywhere.
    """
    sid = sess.id or 0
    for q in db.exec(select(Question).where(Question.session_id == sid)).all():
        for a in db.exec(select(Answer).where(Answer.question_id == q.id)).all():
            db.exec(delete(Evaluation).where(Evaluation.answer_id == a.id))
            db.delete(a)
        db.delete(q)
    report = db.exec(select(MatchReport).where(MatchReport.session_id == sid)).first()
    if report:
        db.exec(delete(MatchItem).where(MatchItem.report_id == report.id))
        db.delete(report)
    db.exec(delete(Scorecard).where(Scorecard.session_id == sid))
    for doc in db.exec(select(Document).where(Document.session_id == sid)).all():
        try:
            Path(doc.storage_path).unlink(missing_ok=True)
        except OSError:
            pass
        db.delete(doc)
    db.commit()
    store.delete_session(user_id=sess.user_id, session_id=sid)
    db.delete(sess)
    db.commit()
