"""SQLite engine + session management via SQLModel."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# Ensure the sqlite directory exists.
_sqlite_path = settings.sqlite_path
if _sqlite_path is not None:
    _sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
)


def init_db() -> None:
    """Create all tables. Import models for side-effect registration."""
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
