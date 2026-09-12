"""Application entry point: lifespan, middleware, exception handlers, routers."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import create_db_and_tables
from app.exceptions import DomainError, domain_error_handler, validation_error_handler
from app.middleware import RequestContextMiddleware
from app.routers import (
    analysis,
    auth,
    documents,
    health,
    interview,
    profile,
    sessions,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    create_db_and_tables()
    logging.getLogger("cvcoach").info(
        "Ready. llm_provider=%s embedding_provider=%s",
        settings.llm_provider,
        settings.embedding_provider,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Upload a CV and a job description; get a grounded gap analysis, "
        "personalised interview questions, rubric-based feedback and a readiness "
        "scorecard. Built for the AUEB 'AI for Developers' final project."
    ),
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # explicit list; never "*" with credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id", "x-process-time-ms"],
)

app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(interview.router)
