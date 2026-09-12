"""Upload -> parse -> section -> parent-child chunk -> embed -> Chroma."""

import hashlib
import logging
import uuid
from pathlib import Path

from sqlmodel import Session, select

from app.config import get_settings
from app.exceptions import InvalidUpload, UnparseablePDF
from app.models import (
    Document,
    DocumentKind,
    DocumentSource,
    IngestStatus,
    InterviewSession,
    SessionStatus,
)
from app.rag import store
from app.rag.chunker import chunk_document
from app.rag.loader import LoadedDocument, load_pdf, load_text

logger = logging.getLogger("cvcoach.ingestion")

PDF_MAGIC = b"%PDF"


def save_upload(
    *, content: bytes, filename: str, session_id: int, user_id: int, kind: DocumentKind, db: Session
) -> Document:
    settings = get_settings()

    if len(content) > settings.max_upload_bytes:
        raise InvalidUpload(
            f"File is {len(content) // 1024}KB; the limit is "
            f"{settings.max_upload_bytes // 1024}KB.",
            {"size_bytes": len(content), "limit": settings.max_upload_bytes},
        )
    # Check the magic bytes, not just the extension.
    if not content.startswith(PDF_MAGIC):
        raise InvalidUpload("That file is not a PDF. Upload a PDF exported from your editor.")

    user_dir = settings.storage_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{uuid.uuid4().hex}.pdf"
    path.write_bytes(content)

    _replace_existing(session_id=session_id, user_id=user_id, kind=kind, db=db)

    doc = Document(
        session_id=session_id,
        kind=kind,
        source=DocumentSource.pdf,
        original_filename=Path(filename).name[:255],
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        storage_path=str(path),
        ingest_status=IngestStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _replace_existing(
    *, session_id: int, user_id: int, kind: DocumentKind, db: Session
) -> None:
    """Re-supplying a document of the same kind replaces the previous one.

    The vectors go too — otherwise the old CV would still be retrievable and the
    analysis would quietly mix two documents.
    """
    existing = db.exec(
        select(Document).where(Document.session_id == session_id, Document.kind == kind)
    ).first()
    if existing:
        store.delete_session(user_id=user_id, session_id=session_id)
        db.delete(existing)
        db.commit()


def save_text(
    *, text: str, title: str, session_id: int, user_id: int, kind: DocumentKind, db: Session
) -> Document:
    """Accept a document as pasted text rather than a file.

    Job descriptions live on web pages, so demanding a PDF forces the user
    through print-to-PDF for no benefit. The stored text feeds exactly the same
    pipeline as an extracted PDF.
    """
    settings = get_settings()
    cleaned = text.strip()

    if len(cleaned.encode("utf-8")) > settings.max_upload_bytes:
        raise InvalidUpload(
            f"That text is {len(cleaned) // 1024}KB; the limit is "
            f"{settings.max_upload_bytes // 1024}KB."
        )

    user_dir = settings.storage_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{uuid.uuid4().hex}.txt"
    path.write_text(cleaned, encoding="utf-8")

    _replace_existing(session_id=session_id, user_id=user_id, kind=kind, db=db)

    doc = Document(
        session_id=session_id,
        kind=kind,
        source=DocumentSource.text,
        original_filename=(title.strip() or "Pasted text")[:255],
        sha256=hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
        size_bytes=len(cleaned.encode("utf-8")),
        storage_path=str(path),
        ingest_status=IngestStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def load_document(doc: Document) -> "LoadedDocument":
    """Read a stored document, whichever way it arrived.

    Every caller goes through here. The analysis service previously called
    load_pdf directly, which meant a pasted job description was parsed as a PDF
    and failed silently.
    """
    load = load_text if doc.source == DocumentSource.text else load_pdf
    return load(Path(doc.storage_path))


def ingest_document(
    document_id: int, user_id: int, db: Session, *, strategy: str = "parent_child"
) -> None:
    """Runs as a background task after the upload endpoint has already responded."""
    doc = db.get(Document, document_id)
    if doc is None:
        return
    doc.ingest_status = IngestStatus.processing
    db.add(doc)
    db.commit()

    try:
        # Purge this document's previous vectors before writing new ones.
        store.delete_document(
            user_id=user_id, session_id=doc.session_id, document_id=doc.id or 0
        )
        loaded = load_document(doc)
        label = "CV" if doc.kind == DocumentKind.cv else "Job description"
        chunked = chunk_document(
            loaded,
            doc_key=f"{doc.kind.value}{doc.id}",
            doc_label=label,
            strategy=strategy,
        )
        count = store.index_document(
            chunked,
            user_id=user_id,
            session_id=doc.session_id,
            document_id=doc.id or 0,
            doc_kind=doc.kind.value,
        )
        doc.page_count = len(loaded.pages)
        doc.char_count = loaded.char_count
        doc.chunk_count = count
        doc.ingest_status = IngestStatus.ready
        doc.ingest_error = None
    except (UnparseablePDF, InvalidUpload) as exc:
        doc.ingest_status = IngestStatus.failed
        doc.ingest_error = exc.message
    except Exception as exc:  # noqa: BLE001 - a background task must never die silently
        logger.exception("Ingestion failed for document %s", document_id)
        doc.ingest_status = IngestStatus.failed
        doc.ingest_error = f"Unexpected error while indexing: {exc}"

    db.add(doc)
    db.commit()
    _refresh_session_status(doc.session_id, db)


def _refresh_session_status(session_id: int, db: Session) -> None:
    docs = db.exec(select(Document).where(Document.session_id == session_id)).all()
    sess = db.get(InterviewSession, session_id)
    if sess is None:
        return
    kinds = {d.kind for d in docs if d.ingest_status == IngestStatus.ready}
    if {DocumentKind.cv, DocumentKind.jd} <= kinds:
        if sess.status in (SessionStatus.created, SessionStatus.ingesting):
            sess.status = SessionStatus.ready
    elif any(d.ingest_status == IngestStatus.processing for d in docs):
        sess.status = SessionStatus.ingesting
    db.add(sess)
    db.commit()


def documents_ready(session_id: int, db: Session) -> bool:
    docs = db.exec(select(Document).where(Document.session_id == session_id)).all()
    ready = {d.kind for d in docs if d.ingest_status == IngestStatus.ready}
    return {DocumentKind.cv, DocumentKind.jd} <= ready
