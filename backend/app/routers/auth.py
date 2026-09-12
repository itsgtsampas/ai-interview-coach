from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.dependencies import CurrentUser, SessionDep
from app.exceptions import AlreadyExists, DomainError
from app.models import User
from app.schemas.auth import RegisterRequest, TokenOut, UserOut
from app.ratelimit import AUTH_LIMIT, REGISTER_LIMIT, limit
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limit(REGISTER_LIMIT)
def register(request: Request, body: RegisterRequest, db: SessionDep) -> User:
    if db.exec(select(User).where(User.email == body.email)).first():
        raise AlreadyExists("An account with that email already exists.")
    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
@limit(AUTH_LIMIT)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SessionDep,
) -> TokenOut:
    # Unauthenticated, so the limiter keys on the client address here. That is
    # the whole point: this is the endpoint someone walks a password list at.
    user = db.exec(select(User).where(User.email == form.username)).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise DomainError("Incorrect email or password.")
    return TokenOut(access_token=create_access_token(user.email))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
