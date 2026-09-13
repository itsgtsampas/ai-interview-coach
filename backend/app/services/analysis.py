"""Stage 1: extract requirements from the JD, then judge each against the CV."""

import logging
from pathlib import Path

from sqlmodel import Session, delete, select

from app.config import get_settings
from app.exceptions import DocumentNotReady, NoRequirementsFound
from app.llm.contracts import MatchReportOut, RequirementsOut
from app.llm.structured import complete_structured
from app.models import (
    Document,
    DocumentKind,
    InterviewSession,
    MatchItem,
    MatchReport,
    SessionStatus,
)
from app.prompts import analyse_match, extract_requirements
from app.rag.retriever import RetrievalConfig, retrieve
from app.services.ingestion import documents_ready, load_document

logger = logging.getLogger("cvcoach.analysis")


def _jd_text(session_id: int, db: Session) -> str:
    doc = db.exec(
        select(Document).where(
            Document.session_id == session_id, Document.kind == DocumentKind.jd
        )
    ).first()
    if doc is None:
        raise DocumentNotReady("No job description has been uploaded for this session.")
    return load_document(doc).full_text


# A model quoting a clause tends to close it with a full stop where the source
# has a comma. That is not a fabrication, so trailing punctuation is not part of
# the comparison - but every other character still has to match, in order.
_QUOTE_EDGE = " .,;:\u00b7\u2014\u2013-\"'\u201c\u201d"


def locate_citation(quote: str | None, passages: list[dict]) -> str | None:
    """Find the quote in the retrieved context and return the SOURCE's own text.

    Returning the source span rather than the model's rendering closes a small
    gap in the grounding promise: what the interface displays is then literally
    the characters in the document, not a retyping of them that might differ in
    punctuation or accent.

    None means the quote is not in the retrieved context - the failure mode this
    check exists for, a confident verdict attached to a sentence the CV never
    contained.
    """
    if not quote:
        return None
    needle = " ".join(quote.split()).strip(_QUOTE_EDGE)
    if not needle:
        return None
    for passage in passages:
        haystack = " ".join(passage["text"].split())
        at = haystack.lower().find(needle.lower())
        if at >= 0:
            return haystack[at : at + len(needle)]
    return None


def verify_citation(quote: str | None, passages: list[dict]) -> bool:
    """Whether a citation appears in the retrieved context at all."""
    return quote is None or locate_citation(quote, passages) is not None


def run_analysis(
    session: InterviewSession, db: Session, config: RetrievalConfig | None = None
) -> MatchReport:
    settings = get_settings()
    if not documents_ready(session.id or 0, db):
        raise DocumentNotReady(
            "Both the CV and the job description must finish indexing before analysis."
        )

    # 1a. Requirements out of the JD (zero-shot).
    reqs_out = complete_structured(
        extract_requirements.render(_jd_text(session.id or 0, db)),
        RequirementsOut,
        db=db,
        session_id=session.id,
        model=settings.openai_chat_model_small,
        temperature=0.0,
    )
    requirements = [r.model_dump() for r in reqs_out.requirements]
    if not requirements:
        # Without requirements every CV matches perfectly, which is worse than
        # no answer: the user would act on a score that means nothing.
        raise NoRequirementsFound(
            "No requirements could be read from this job description. Check that "
            "you pasted the full posting, including the section listing what the "
            "role needs — not just the company description.",
            {"session_id": session.id},
        )

    # 1b. Retrieve CV evidence for each requirement.
    evidence: dict[str, list[dict]] = {}
    for idx, req in enumerate(requirements):
        passages = retrieve(
            req["text"],
            user_id=session.user_id,
            session_id=session.id or 0,
            doc_kind="cv",
            config=config,
        )
        evidence[str(idx)] = [p.as_dict() for p in passages]

    # 1c. Judge, with chain-of-thought and mandatory citations.
    report_out = complete_structured(
        analyse_match.render(requirements, evidence),
        MatchReportOut,
        db=db,
        session_id=session.id,
        model=settings.openai_chat_model_large,
        temperature=0.2,
    )

    # Second line of grounding defence: strip any citation the context does not contain.
    for idx, item in enumerate(report_out.items):
        found = locate_citation(item.evidence_quote, evidence.get(str(idx), []))
        if item.evidence_quote and found:
            # Show the document's characters, not the model's retyping of them.
            item.evidence_quote = found
        elif item.evidence_quote:
            # A verdict whose citation cannot be verified becomes "missing", not
            # "partial". Keeping a claim after discarding the sentence behind it
            # is the one thing this product promises never to do, and it is what
            # the prompt itself instructs: if there is no such sentence, the
            # status is missing.
            logger.warning("Dropped an unverifiable citation on item %s", idx)
            item.evidence_quote = None
            item.evidence_page = None
            item.evidence_chunk_id = None
            item.evidence_section = None
            item.status = "missing"

    existing = db.exec(
        select(MatchReport).where(MatchReport.session_id == session.id)
    ).first()
    if existing:
        db.exec(delete(MatchItem).where(MatchItem.report_id == existing.id))
        db.delete(existing)
        db.commit()

    report = MatchReport(
        session_id=session.id or 0,
        overall_score=report_out.overall_score,
        verdict=report_out.verdict,
        summary=report_out.summary,
        prompt_version=analyse_match.VERSION,
        model=settings.openai_chat_model_large,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    for order, item in enumerate(report_out.items):
        db.add(MatchItem(
            report_id=report.id or 0,
            requirement=item.requirement,
            category=item.category,
            kind=item.kind,
            status=item.status,
            confidence=item.confidence,
            evidence_quote=item.evidence_quote,
            evidence_page=item.evidence_page,
            evidence_chunk_id=item.evidence_chunk_id,
            evidence_section=item.evidence_section,
            reasoning=item.reasoning,
            order_index=order,
        ))
    session.status = SessionStatus.analysed
    db.add(session)
    db.commit()
    db.refresh(report)
    return report


def get_report(session_id: int, db: Session) -> tuple[MatchReport | None, list[MatchItem]]:
    report = db.exec(select(MatchReport).where(MatchReport.session_id == session_id)).first()
    if report is None:
        return None, []
    items = db.exec(
        select(MatchItem).where(MatchItem.report_id == report.id).order_by(MatchItem.order_index)
    ).all()
    return report, list(items)
