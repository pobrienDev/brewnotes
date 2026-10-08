"""Engine, session dependency and metadata naming convention."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings

# Every constraint gets a stable, predictable name so migrations can refer to it later.
# This must be in place before the first migration is written.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create the engine. pool_size + max_overflow across all instances must stay under the
    database's connection limit, and every statement runs under a server-side timeout."""
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_timeout=10,
        connect_args={
            "connect_timeout": settings.db_connect_timeout_s,
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
        },
    )


SessionFactory = sessionmaker[Session]


def get_db(request: Request) -> Iterator[Session]:
    """One transaction per request: committed when the route returns, rolled back on error."""
    session_factory: SessionFactory = request.app.state.session_factory
    with session_factory() as session, session.begin():
        yield session
