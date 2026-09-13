"""Stage 7: a cover letter built only from requirements the CV evidenced.

Grounding is structural, not instructional: unevidenced requirements go to the
prompt in a separate list so they can be named as forbidden, and evidenced ones
arrive with the sentence that earned them.
"""

import json
import re
from collections.abc import Iterator

from sqlmodel import Session, select

from app.config import get_settings
from app.exceptions import StageNotReady
from app.llm.contracts import CoverLetterOut
from app.llm.structured import complete_stream, complete_structured
from app.models import CoverLetter, EvidenceStatus, InterviewSession
from app.prompts import cover_letter
from app.services.analysis import get_report
from app.textutil import tokens

TONES = ("plain", "warm", "formal")

# A CV bullet opens with a past-tense verb; a section heading or a job title
# does not. That one signal separates "Designed the PostgreSQL schema..." from
# "Senior Backend Engineer, Nexora Commerce (2021-2024)".
_ACHIEVEMENT = re.compile(r"^[A-Z][a-z]+(?:ed|t|lt|ught|ade)\b")


def company_from(title: str, role: str) -> str:
    """The employer's name from a session title shaped "Company - Role"."""
    head = re.split(r"\s+[-\u2013\u2014]\s+", title.strip(), maxsplit=1)[0].strip()
    if not head:
        return title.strip()
    # If the user named the session after the role rather than the employer,
    # there is no company here to use and a generic address is more honest.
    if role and len(set(tokens(head)) - set(tokens(role))) == 0:
        return ""
    return head


def _restates_the_role(requirement: str, role: str) -> bool:
    """Whether this "requirement" is just the job title restated.

    Extractors sometimes lift the posting's headline out as a requirement.
    """
    if not role:
        return False
    a, b = set(tokens(requirement)), set(tokens(role))
    return bool(a) and bool(b) and len(a - b) <= 1


def _is_achievement(quote: str | None) -> bool:
    if not quote:
        return False
    text = quote.strip()
    # A date range is the giveaway for a role header.
    if re.search(r"\(\s*\d{4}\s*[-\u2013]\s*(?:\d{4}|present)\s*\)", text, re.I):
        return False
    return bool(_ACHIEVEMENT.match(text)) and len(text.split()) >= 6


# How many evidenced requirements the letter turns into paragraphs. Three is
# where cover letters start repeating themselves.
LETTER_PARAGRAPHS = 2


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
        if i.status == EvidenceStatus.strong
        and i.evidence_quote
        and not _restates_the_role(i.requirement, session.target_role)
    ]
    # Achievements before confidence: only a quote describing work can be
    # rewritten into a first-person claim. A job heading cannot.
    evidenced.sort(key=lambda e: (_is_achievement(e["quote"]), e["confidence"]), reverse=True)

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
            company=company_from(session.title, session.target_role),
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
    """Yield the body in pieces, then persist it.

    Persistence happens after the last piece, so a disconnect leaves no
    half-written letter behind.
    """
    settings = get_settings()
    tone = tone if tone in TONES else "plain"
    evidenced, unevidenced = _material(session, db)

    prompt = cover_letter.render(
        role=session.target_role,
        company=company_from(session.title, session.target_role),
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
        [e["requirement"] for e in evidenced[:LETTER_PARAGRAPHS]],
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
