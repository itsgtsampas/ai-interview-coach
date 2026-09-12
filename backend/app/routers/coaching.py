"""Bullet rewrites and cover letters.

The cover letter has both a blocking and a streaming endpoint. They render the
same prompt and persist the same row; the streaming one exists because a letter
is 200 words of prose and watching it arrive is the difference between "the app
is working" and "the app has frozen".
"""

import json
import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app import sse
from app.db import engine
from app.dependencies import OwnedSession, SessionDep
from app.exceptions import DomainError
from app.models import CvSuggestion
from app.ratelimit import GENERATE_LIMIT, limit
from app.schemas.coaching import CoverLetterOut, CoverLetterRequest, SuggestionOut
from app.services import cover_letter as letters
from app.services import rewrite

logger = logging.getLogger("cvcoach.coaching")
router = APIRouter(prefix="/api/v1", tags=["coaching"])


def _suggestion_out(row: CvSuggestion) -> SuggestionOut:
    return SuggestionOut(
        id=row.id or 0,
        match_item_id=row.match_item_id,
        requirement=row.requirement,
        bullet=row.bullet,
        premise=row.premise,
        why=row.why,
        if_you_cannot=row.if_you_cannot,
        placeholders=row.placeholders,
        prompt_version=row.prompt_version,
    )


@router.post(
    "/sessions/{session_id}/match-items/{item_id}/rewrite",
    response_model=SuggestionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Suggest a CV bullet for one unmet requirement",
)
@limit(GENERATE_LIMIT)
def rewrite_bullet(
    request: Request, item_id: int, sess: OwnedSession, db: SessionDep
) -> SuggestionOut:
    return _suggestion_out(rewrite.suggest(item_id, sess, db))


@router.get("/sessions/{session_id}/rewrites", response_model=list[SuggestionOut])
def list_rewrites(sess: OwnedSession, db: SessionDep) -> list[SuggestionOut]:
    return [_suggestion_out(r) for r in rewrite.list_for_session(sess.id or 0, db)]


def _letter_out(row) -> CoverLetterOut:
    return CoverLetterOut(
        id=row.id or 0,
        session_id=row.session_id,
        tone=row.tone,
        subject=row.subject,
        body=row.body,
        claims_used=row.claims_used,
        prompt_version=row.prompt_version,
        created_at=row.created_at,
    )


@router.get("/sessions/{session_id}/cover-letter", response_model=CoverLetterOut)
def read_cover_letter(sess: OwnedSession, db: SessionDep) -> CoverLetterOut:
    row = letters.get(sess.id or 0, db)
    if row is None:
        from app.exceptions import NotFound

        raise NotFound("No cover letter has been written for this session yet.")
    return _letter_out(row)


@router.post(
    "/sessions/{session_id}/cover-letter",
    response_model=CoverLetterOut,
    status_code=status.HTTP_201_CREATED,
)
@limit(GENERATE_LIMIT)
def write_cover_letter(
    request: Request, body: CoverLetterRequest, sess: OwnedSession, db: SessionDep
) -> CoverLetterOut:
    return _letter_out(letters.generate(sess, db, tone=body.tone))


@router.post("/sessions/{session_id}/cover-letter/stream")
@limit(GENERATE_LIMIT)
def stream_cover_letter(
    request: Request, body: CoverLetterRequest, sess: OwnedSession
) -> StreamingResponse:
    """The same letter, delivered as it is written.

    The dependency-injected DB session is deliberately not used here. It is
    closed when this function returns, which for a streaming response is *before*
    the generator runs; the generator opens its own session and owns its lifetime.
    """
    session_id = sess.id or 0
    tone = body.tone

    def events():
        with Session(engine) as db:
            target = db.get(type(sess), session_id)
            if target is None:
                yield sse.error("not_found", "That session no longer exists.")
                return
            try:
                yield sse.stage("grounding", "Collecting the claims your CV evidences")
                for piece in letters.stream(target, db, tone=tone):
                    yield sse.token(piece)
                row = letters.get(session_id, db)
                yield sse.done(json.loads(_letter_out(row).model_dump_json()))
            except DomainError as exc:
                yield sse.error(exc.code, exc.message, exc.details)
            except Exception:  # noqa: BLE001
                # The status line is long gone by the time this fires, so an
                # exception cannot become a 500 — it has to travel as an event.
                logger.exception("cover letter stream failed")
                yield sse.error("stream_failed", "Writing the letter failed part-way.")

    return StreamingResponse(
        events(), media_type="text/event-stream", headers=sse.SSE_HEADERS
    )
