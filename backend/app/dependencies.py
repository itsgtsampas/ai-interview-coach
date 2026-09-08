"""Shared dependencies: DB session, current user, pagination, RAG/LLM singletons."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.db import get_session
from app.models import InterviewSession, User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep
) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = decode_access_token(token)
    if email is None:
        raise creds_exc
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not user.is_active:
        raise creds_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def owned_session(session_id: int, session: SessionDep, user: CurrentUser) -> InterviewSession:
    """Fetch a session the caller owns.

    Returns 404 rather than 403 for someone else's session: a 403 would confirm
    that the id exists.
    """
    obj = session.get(InterviewSession, session_id)
    if obj is None or obj.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


OwnedSession = Annotated[InterviewSession, Depends(owned_session)]


class Pagination:
    def __init__(self, skip: int = 0, limit: int = 20):
        self.skip = max(0, skip)
        self.limit = min(max(1, limit), 100)


PageDep = Annotated[Pagination, Depends(Pagination)]
