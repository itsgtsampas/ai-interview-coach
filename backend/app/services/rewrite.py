"""Stage 6: turn one unmet requirement into a CV bullet the candidate can adapt.

Retrieval is reused rather than re-invented: the bullet is written against the
passages the CV actually offers for this requirement, so the "premise" line can
say truthfully whether there was anything adjacent to build on.
"""

import json

from sqlmodel import Session, delete, select

from app.config import get_settings
from app.exceptions import NotFound, StageNotReady
from app.llm.contracts import RewriteOut
from app.llm.structured import complete_structured
from app.models import CvSuggestion, InterviewSession, MatchItem, MatchReport
from app.prompts import rewrite_bullet
from app.rag.retriever import retrieve

# A bullet with no placeholders and no evidence behind it is a fabricated claim
# wearing a suggestion's clothes. See prompts/rewrite_bullet.py for why this is
# the failure mode worth a guard rather than a code review comment.
MIN_PLACEHOLDERS_WHEN_UNEVIDENCED = 1


def _owned_item(item_id: int, session: InterviewSession, db: Session) -> MatchItem:
    item = db.get(MatchItem, item_id)
    if item is None:
        raise NotFound("That requirement does not exist.")
    report = db.get(MatchReport, item.report_id)
    if report is None or report.session_id != session.id:
        raise NotFound("That requirement does not exist.")
    return item


def suggest(item_id: int, session: InterviewSession, db: Session) -> CvSuggestion:
    settings = get_settings()
    item = _owned_item(item_id, session, db)

    if item.status.value == "strong":
        raise StageNotReady(
            "This requirement is already evidenced in your CV. Rewrites are for the "
            "thin and missing ones."
        )

    existing = db.exec(
        select(CvSuggestion).where(CvSuggestion.match_item_id == item_id)
    ).first()
    if existing:
        return existing

    passages = retrieve(
        item.requirement,
        user_id=session.user_id,
        session_id=session.id or 0,
        doc_kind="cv",
    )
    cv_context = "\n\n".join(p.text for p in passages[:3])

    out = complete_structured(
        rewrite_bullet.render(
            requirement=item.requirement,
            status=item.status.value,
            evidence=item.evidence_quote,
            cv_context=cv_context,
        ),
        RewriteOut,
        db=db,
        session_id=session.id,
        model=settings.openai_chat_model_small,
        temperature=0.4,
    )

    if not item.evidence_quote and len(out.placeholders) < MIN_PLACEHOLDERS_WHEN_UNEVIDENCED:
        raise StageNotReady(
            "The suggestion came back as a finished claim rather than a template, and "
            "your CV has no evidence for this requirement. Refusing to show it."
        )

    row = CvSuggestion(
        session_id=session.id or 0,
        match_item_id=item_id,
        requirement=item.requirement,
        bullet=out.bullet,
        premise=out.premise,
        why=out.why,
        if_you_cannot=out.if_you_cannot,
        placeholders_json=json.dumps(out.placeholders),
        prompt_version=rewrite_bullet.VERSION,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_for_session(session_id: int, db: Session) -> list[CvSuggestion]:
    return list(
        db.exec(select(CvSuggestion).where(CvSuggestion.session_id == session_id)).all()
    )


def clear_for_session(session_id: int, db: Session) -> None:
    db.exec(delete(CvSuggestion).where(CvSuggestion.session_id == session_id))
    db.commit()
