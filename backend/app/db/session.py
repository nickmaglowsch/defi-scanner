from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ponytail: default pool sizing (5 connections, 10 overflow). NullPool would be
# simpler for single-worker but breaks under any concurrency; default pool is the
# safe lazy choice.
engine = create_async_engine(settings.DATABASE_URL, echo=False)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency: yields an async database session."""
    async with async_session_factory() as session:
        yield session
