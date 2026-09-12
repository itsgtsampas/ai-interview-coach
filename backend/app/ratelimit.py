"""Per-caller request ceilings.

Three endpoint groups need a ceiling, for three different reasons:

* ``auth``     - an unlimited login endpoint is an open brute-force target.
* ``generate`` - every call here reaches a model. With a real provider
                 configured that is money, so an accidental loop in the client
                 (or a bored visitor) spends it.
* ``upload``   - PDFs land on disk and in the vector store; unbounded uploads
                 fill both.

Keying: authenticated callers are limited by user id, so one tenant cannot
exhaust another's budget and a shared NAT address is not a shared ceiling.
Anonymous callers fall back to the client address, which is all we have before
a token exists.
"""

from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings

# Tier names are used as decorators throughout the routers, so the numbers live
# in one place and the documentation can quote them.
AUTH_LIMIT = "5/minute"
REGISTER_LIMIT = "10/hour"
GENERATE_LIMIT = "30/hour"
UPLOAD_LIMIT = "40/hour"


def caller_key(request: Request) -> str:
    """User id when we have one, client address otherwise.

    ``request.state.user_id`` is set by the auth dependency. It is absent on
    unauthenticated routes and on requests that fail authentication, which is
    exactly when the address is the right key.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=caller_key,
    # Tests and local development would otherwise trip the auth ceiling on the
    # fourth login of a run; the flag is off in every other environment.
    enabled=not get_settings().disable_rate_limits,
    # X-RateLimit-* injection requires every limited endpoint to declare a
    # `response: Response` parameter. That is ten noisy signatures to advertise a
    # budget nothing reads; the header that matters, Retry-After, is set on the
    # 429 itself in rate_limit_handler below.
    headers_enabled=False,
)


def rate_limit_handler(request: Request, exc: Exception) -> Response:
    """Render 429 in the application's single error shape (see exceptions.py)."""
    detail = getattr(exc, "detail", "Too many requests.")
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "message": (
                "You have made too many requests. Wait a moment and try again."
            ),
            "details": {"limit": str(detail)},
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"Retry-After": "60"},
    )


def install(app) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


def limit(spec: str) -> Callable:
    """Thin alias so routers read `@limit(GENERATE_LIMIT)` and never import slowapi."""
    return limiter.limit(spec)
