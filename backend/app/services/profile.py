"""Profile storage, and seeding a new session from it."""

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.config import get_settings
from app.exceptions import InvalidUpload, NotFound
from app.models import Document, DocumentKind, DocumentSource, IngestStatus, UserProfile
from app.rag.loader import load_pdf

PDF_MAGIC = b"%PDF"


def get_or_create(user_id: int, db: Session) -> UserProfile:
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def save_cv(*, content: bytes, filename: str, user_id: int, db: Session) -> UserProfile:
    """Store the CV the user reuses across applications."""
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise InvalidUpload(
            f"File is {len(content) // 1024}KB; the limit is "
            f"{settings.max_upload_bytes // 1024}KB."
        )
    if not content.startswith(PDF_MAGIC):
        raise InvalidUpload("That file is not a PDF. Upload a PDF exported from your editor.")

    profile = get_or_create(user_id, db)
    user_dir = settings.storage_dir / str(user_id) / "profile"
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{uuid.uuid4().hex}.pdf"
    path.write_bytes(content)

    # Parse now rather than at session time, so a bad file is reported while the
    # user is looking at the upload instead of three screens later.
    pages = load_pdf(path).pages

    if profile.cv_storage_path:
        Path(profile.cv_storage_path).unlink(missing_ok=True)

    profile.cv_filename = Path(filename).name[:255]
    profile.cv_storage_path = str(path)
    profile.cv_size_bytes = len(content)
    profile.cv_page_count = len(pages)
    profile.cv_uploaded_at = datetime.now(timezone.utc)
    profile.updated_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def delete_cv(user_id: int, db: Session) -> UserProfile:
    profile = get_or_create(user_id, db)
    if not profile.cv_storage_path:
        raise NotFound("No CV is stored on your profile.")
    Path(profile.cv_storage_path).unlink(missing_ok=True)
    profile.cv_filename = ""
    profile.cv_storage_path = ""
    profile.cv_size_bytes = 0
    profile.cv_page_count = 0
    profile.cv_uploaded_at = None
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def attach_cv_to_session(*, session_id: int, user_id: int, db: Session) -> Document | None:
    """Give a new session its own copy of the profile CV.

    A copy, not a reference: a session owns its documents, its vectors are
    scoped to it, and deleting one must not reach back into the profile. It also
    means replacing the CV inside a session leaves the profile untouched, which
    is what "use a different CV for this application" should do.
    """
    profile = db.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()
    if profile is None or not profile.cv_storage_path:
        return None
    source = Path(profile.cv_storage_path)
    if not source.exists():
        return None

    settings = get_settings()
    user_dir = settings.storage_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / f"{uuid.uuid4().hex}.pdf"
    shutil.copy2(source, destination)

    content = destination.read_bytes()
    doc = Document(
        session_id=session_id,
        kind=DocumentKind.cv,
        source=DocumentSource.pdf,
        original_filename=profile.cv_filename or "cv.pdf",
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        storage_path=str(destination),
        ingest_status=IngestStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc
