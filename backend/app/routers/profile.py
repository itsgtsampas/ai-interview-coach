"""Profile endpoints: the details and CV a candidate reuses across applications."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.dependencies import CurrentUser, SessionDep
from app.models import UserProfile
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services import profile as service

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _serialise(profile: UserProfile, user) -> ProfileOut:
    return ProfileOut(
        id=profile.id or 0,
        full_name=user.full_name,
        email=user.email,
        age=profile.age,
        has_cv=profile.has_cv,
        cv_filename=profile.cv_filename,
        cv_page_count=profile.cv_page_count,
        cv_uploaded_at=profile.cv_uploaded_at,
        updated_at=profile.updated_at,
        **ProfileUpdate.model_validate(profile, from_attributes=True).model_dump(),
    )


@router.get("", response_model=ProfileOut)
def read_profile(user: CurrentUser, db: SessionDep) -> ProfileOut:
    return _serialise(service.get_or_create(user.id or 0, db), user)


@router.put("", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, user: CurrentUser, db: SessionDep) -> ProfileOut:
    from datetime import datetime, timezone

    profile = service.get_or_create(user.id or 0, db)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialise(profile, user)


@router.post("/cv", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
async def upload_profile_cv(
    user: CurrentUser, db: SessionDep, file: Annotated[UploadFile, File()]
) -> ProfileOut:
    """The CV new sessions start from. Each session takes its own copy."""
    profile = service.save_cv(
        content=await file.read(),
        filename=file.filename or "cv.pdf",
        user_id=user.id or 0,
        db=db,
    )
    return _serialise(profile, user)


@router.delete("/cv", response_model=ProfileOut)
def delete_profile_cv(user: CurrentUser, db: SessionDep) -> ProfileOut:
    return _serialise(service.delete_cv(user.id or 0, db), user)
