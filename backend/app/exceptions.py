"""Domain exceptions plus the handlers that map them to a single JSON error shape.

Services raise these; they never import fastapi.HTTPException.  That keeps the
service layer free of HTTP concerns (see DESIGN.md section 3.2).
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    code = "domain_error"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFound(DomainError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class AlreadyExists(DomainError):
    code = "already_exists"
    status_code = status.HTTP_409_CONFLICT


class DocumentNotReady(DomainError):
    code = "documents_not_ready"
    status_code = status.HTTP_409_CONFLICT


class UnparseablePDF(DomainError):
    code = "unparseable_pdf"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class InvalidUpload(DomainError):
    code = "invalid_upload"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class NoRequirementsFound(DomainError):
    """The job description parsed, but no requirements could be read from it.

    Scoring a CV against nothing produces a meaningless perfect match, so this
    is surfaced to the user instead.
    """

    code = "no_requirements_found"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class StageNotReady(DomainError):
    code = "stage_not_ready"
    status_code = status.HTTP_409_CONFLICT


class LLMOutputError(DomainError):
    code = "llm_output_invalid"
    status_code = status.HTTP_502_BAD_GATEWAY


class ProviderUnavailable(DomainError):
    code = "provider_unavailable"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


def _payload(request: Request, code: str, message: str, details: dict) -> dict:
    return {
        "error": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
        "details": details,
    }


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(request, exc.code, exc.message, exc.details),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    issues = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "problem": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_payload(
            request,
            "invalid_request",
            "The request body or parameters failed validation.",
            {"issues": issues},
        ),
    )
