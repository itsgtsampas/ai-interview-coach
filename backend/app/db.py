"""Engine and per-request session dependency (one engine per process, one session per request)."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()
settings.ensure_dirs()

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite only
)


def create_db_and_tables() -> None:
    # Import for side effects so SQLModel.metadata knows every table.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
