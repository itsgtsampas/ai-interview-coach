"""Progress across every application, not inside one.

Read-only aggregation of stored rows — no model is called, so this endpoint is
free and its numbers are reproducible.
"""

from fastapi import APIRouter

from app.dependencies import CurrentUser, SessionDep
from app.schemas.progress import ProgressOut
from app.services.progress import build

router = APIRouter(prefix="/api/v1", tags=["progress"])


@router.get("/progress", response_model=ProgressOut, summary="Scores across all sessions")
def read_progress(user: CurrentUser, db: SessionDep) -> ProgressOut:
    return ProgressOut.model_validate(build(user.id or 0, db))
