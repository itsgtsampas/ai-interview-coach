from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status
from sqlmodel import Session, select

from app.db import engine
from app.dependencies import CurrentUser, OwnedSession, SessionDep
from app.models import Document, DocumentKind, SessionStatus
from app.schemas.session import DocumentOut
from app.services.ingestion import ingest_document, save_upload

router = APIRouter(prefix="/api/v1/sessions", tags=["documents"])


def _ingest_in_background(document_id: int, user_id: int) -> None:
    # Background tasks outlive the request, so they get their own session.
    with Session(engine) as db:
        ingest_document(document_id, user_id, db)


@router.post(
    "/{session_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    sess: OwnedSession,
    user: CurrentUser,
    db: SessionDep,
    background: BackgroundTasks,
    kind: Annotated[DocumentKind, Query(description="cv or jd")],
    file: Annotated[UploadFile, File()],
) -> DocumentOut:
    """Accepts the file, returns immediately, indexes in the background.

    Parsing and embedding take seconds; the client polls GET .../documents.
    """
    content = await file.read()
    doc = save_upload(
        content=content,
        filename=file.filename or "upload.pdf",
        session_id=sess.id or 0,
        user_id=user.id or 0,
        kind=kind,
        db=db,
    )
    sess.status = SessionStatus.ingesting
    db.add(sess)
    db.commit()
    background.add_task(_ingest_in_background, doc.id or 0, user.id or 0)
    return DocumentOut.model_validate(doc, from_attributes=True)


@router.get("/{session_id}/documents", response_model=list[DocumentOut])
def list_documents(sess: OwnedSession, db: SessionDep) -> list[DocumentOut]:
    docs = db.exec(select(Document).where(Document.session_id == sess.id)).all()
    return [DocumentOut.model_validate(d, from_attributes=True) for d in docs]
