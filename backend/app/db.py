"""Engine and per-request session dependency (one engine per process, one session per request)."""

from collections.abc import Iterator

import logging

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

logger = logging.getLogger("cvcoach.db")

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
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Add columns that exist in the models but not yet in the database.

    create_all() creates missing tables and nothing else, so every new field has
    meant deleting the development database and reseeding — three times so far,
    losing a real user account on one of them. This closes that gap for the
    additive case, which is the only one that has come up.

    It is not a migrations system: it will not rename, drop, retype or backfill,
    and it does not record what it did. Anything beyond adding a nullable column
    still needs Alembic (see DESIGN.md 14.3).
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            if not column.nullable and column.default is None and column.server_default is None:
                logger.warning(
                    "Cannot add required column %s.%s automatically; it needs a "
                    "migration.", table.name, column.name,
                )
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" ' \
                  f"{column.type.compile(engine.dialect)}"
            default = getattr(column.default, "arg", None)
            if default is not None and not callable(default):
                literal = f"'{default}'" if isinstance(default, str) else str(default)
                ddl += f" DEFAULT {literal}"
            with engine.begin() as connection:
                connection.execute(text(ddl))
            logger.info("Added missing column %s.%s", table.name, column.name)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
