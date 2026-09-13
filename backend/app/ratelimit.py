"""Per-caller request ceilings.

Three groups, three reasons: an uncapped login is a brute-force target, every
generate call costs money, and uploads fill the disk and the vector store.

Authenticated callers are keyed by user id so one tenant cannot exhaust
another's budget; anonymous callers fall back to the client address.
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
    """User id when authenticated, client address otherwise."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=caller_key,
    # The test suite would otherwise trip the auth ceiling within seconds.
    enabled=not get_settings().disable_rate_limits,
    # X-RateLimit-* would need a `response: Response` param on every endpoint;
    # Retry-After on the 429 is the header that actually matters.
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
