"""Async database engine, session factory, and the per-request session dependency.

One Postgres, one engine per process (ADR-001/006). Modules own their own tables
(05 §2); cross-module reads go through `service.py`, never another module's models.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,  # log SQL in dev so N+1s are visible (05 §12)
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base shared by every module's models.

    Alembic autogenerate imports this metadata; a module's models are only seen
    by a migration if that module is imported in migrations/env.py.
    """


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
