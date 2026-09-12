"""File exports.

Served as a normal authenticated JSON-API route returning bytes rather than a
signed public URL: the scorecard quotes the candidate's CV, so it must not be
reachable by anyone holding a link.
"""

from fastapi import APIRouter, Request, Response

from app.dependencies import OwnedSession, SessionDep
from app.ratelimit import UPLOAD_LIMIT, limit
from app.services.pdf_export import build, filename_for

router = APIRouter(prefix="/api/v1/sessions", tags=["export"])


@router.get(
    "/{session_id}/scorecard.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The scorecard"}},
    summary="Download the scorecard as a PDF",
)
@limit(UPLOAD_LIMIT)
def scorecard_pdf(request: Request, sess: OwnedSession, db: SessionDep) -> Response:
    return Response(
        content=build(sess, db),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_for(sess)}"',
            # The browser fetches this with an Authorization header and turns it
            # into a blob, so it must not sit in a shared cache.
            "Cache-Control": "private, no-store",
        },
    )
