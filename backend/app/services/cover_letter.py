"""Stage 7: a cover letter built only from requirements the CV evidenced.

The grounding is structural rather than instructional. Unevidenced requirements
are passed to the prompt in a separate list precisely so they can be named as
forbidden, and the strong ones arrive with the sentence that earned them — so
the letter is a rearrangement of things already proven, not a new set of claims.
"""

import json
from collections.abc import Iterator

from sqlmodel import Session, select

from app.config import get_settings
from app.exceptions import StageNotReady
from app.llm.contracts import CoverLetterOut
from app.llm.structured import complete_stream, complete_structured
from app.models import CoverLetter, EvidenceStatus, InterviewSession
from app.prompts import cover_letter
from app.services.analysis import get_report

TONES = ("plain", "warm", "formal")


def _material(session: InterviewSession, db: Session) -> tuple[list[dict], list[str]]:
    """The evidenced claims and the forbidden ones, in the order the letter wants them."""
    report, items = get_report(session.id or 0, db)
    if report is None:
        raise StageNotReady("Run the gap analysis before writing a cover letter.")

    evidenced = [
        {
            "requirement": i.requirement,
            "quote": i.evidence_quote,
            "confidence": round(i.confidence, 2),
        }
        for i in items
        if i.status == EvidenceStatus.strong and i.evidence_quote
    ]
    # Strongest first: the opening sentence uses whatever is at the head of this
    # list, and that sentence is the only one a hiring manager reliably reads.
    evidenced.sort(key=lambda e: e["confidence"], reverse=True)

    # Only must-haves are worth acknowledging. Listing every nice-to-have the CV
    # lacks turns a cover letter into a confession.
    unevidenced = [
        i.requirement
        for i in items
        if i.status == EvidenceStatus.missing
        and i.category.value == "must_have"
        and i.kind.value == "evidenceable"
    ]
    return evidenced, unevidenced


def generate(session: InterviewSession, db: Session, tone: str = "plain") -> CoverLetter:
    """Non-streaming path: used by the eval harness and any client that wants it whole."""
    settings = get_settings()
    tone = tone if tone in TONES else "plain"
    evidenced, unevidenced = _material(session, db)

    out = complete_structured(
        cover_letter.render(
            role=session.target_role,
            company=session.title,
            evidenced=evidenced,
            unevidenced=unevidenced,
            tone=tone,
        ),
        CoverLetterOut,
        db=db,
        session_id=session.id,
        model=settings.openai_chat_model_large,
        temperature=0.4,
    )
    return _store(session, db, tone, out.subject, out.body, out.claims_used)


def stream(session: InterviewSession, db: Session, tone: str = "plain") -> Iterator[str]:
    """Streaming path: yields the body in pieces, then persists the whole thing.

    The caller frames these as SSE `token` events. Persistence happens after the
    last piece, so a reader who disconnects halfway leaves no half-written letter
    in the database.
    """
    settings = get_settings()
    tone = tone if tone in TONES else "plain"
    evidenced, unevidenced = _material(session, db)

    prompt = cover_letter.render(
        role=session.target_role,
        company=session.title,
        evidenced=evidenced,
        unevidenced=unevidenced,
        tone=tone,
    )

    parts: list[str] = []
    for piece in complete_stream(
        prompt,
        db=db,
        session_id=session.id,
        model=settings.openai_chat_model_large,
        temperature=0.4,
    ):
        parts.append(piece)
        yield piece

    _store(
        session,
        db,
        tone,
        f"Application — {session.target_role or session.title}",
        "".join(parts),
        [e["requirement"] for e in evidenced[:2]],
    )


def _store(
    session: InterviewSession,
    db: Session,
    tone: str,
    subject: str,
    body: str,
    claims: list[str],
) -> CoverLetter:
    existing = db.exec(
        select(CoverLetter).where(CoverLetter.session_id == session.id)
    ).first()
    if existing:
        db.delete(existing)
        db.commit()

    row = CoverLetter(
        session_id=session.id or 0,
        tone=tone,
        subject=subject,
        body=body,
        claims_used_json=json.dumps(claims),
        prompt_version=cover_letter.VERSION,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get(session_id: int, db: Session) -> CoverLetter | None:
    return db.exec(select(CoverLetter).where(CoverLetter.session_id == session_id)).first()
