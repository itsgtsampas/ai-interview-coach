from fastapi import APIRouter, Request

from app.dependencies import OwnedSession, SessionDep
from app.exceptions import NotFound
from app.models.analysis import EvidenceStatus
from app.ratelimit import GENERATE_LIMIT, limit
from app.schemas.analysis import MatchItemOut, MatchReportOut
from app.services.analysis import get_report, run_analysis

router = APIRouter(prefix="/api/v1/sessions", tags=["analysis"])


def _serialise(report, items) -> MatchReportOut:
    counts = {s.value: 0 for s in EvidenceStatus}
    for i in items:
        if str(getattr(i.kind, "value", i.kind)) == "behavioural":
            continue  # excluded from the score, so excluded from its tally
        key = i.status.value if hasattr(i.status, "value") else str(i.status)
        counts[key] = counts.get(key, 0) + 1
    return MatchReportOut(
        id=report.id,
        session_id=report.session_id,
        overall_score=report.overall_score,
        verdict=report.verdict,
        summary=report.summary,
        prompt_version=report.prompt_version,
        items=[
            MatchItemOut(
                id=i.id,
                requirement=i.requirement,
                category=i.category,
                kind=i.kind,
                status=i.status,
                confidence=i.confidence,
                reasoning=i.reasoning,
                evidence_quote=i.evidence_quote,
                evidence_page=i.evidence_page,
                evidence_section=i.evidence_section,
            )
            for i in items
        ],
        counts=counts,
    )


@router.post("/{session_id}/analysis", response_model=MatchReportOut)
@limit(GENERATE_LIMIT)
def create_analysis(request: Request, sess: OwnedSession, db: SessionDep) -> MatchReportOut:
    report = run_analysis(sess, db)
    _, items = get_report(sess.id or 0, db)
    return _serialise(report, items)


@router.get("/{session_id}/analysis", response_model=MatchReportOut)
def read_analysis(sess: OwnedSession, db: SessionDep) -> MatchReportOut:
    report, items = get_report(sess.id or 0, db)
    if report is None:
        raise NotFound("No analysis has been run for this session yet.")
    return _serialise(report, items)
