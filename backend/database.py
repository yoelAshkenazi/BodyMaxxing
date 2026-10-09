"""Asynchronous PostgreSQL / SQLite connection pooling and transactional session management."""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost:5432/fitness_db",
)


def build_async_engine(database_url: str = DATABASE_URL) -> AsyncEngine:
    """Builds an async engine configured with connection pooling.
    
    Uses connection pooling parameters for PostgreSQL, while gracefully handling SQLite
    for lightweight testing and Pyodide/local simulation environments.
    """
    if "sqlite" in database_url:
        return create_async_engine(
            database_url,
            echo=False,
            future=True,
        )
    return create_async_engine(
        database_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        future=True,
    )


engine: AsyncEngine = build_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session_context(
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> AsyncGenerator[AsyncSession, None]:
    """Context manager ensuring explicit commit on success or rollback on error."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends dependency providing an async transactional session.
    
    Guarantees that database sessions are not leaked across event-loop tasks.
    """
    async with get_session_context() as session:
        yield session


async def init_db(target_engine: AsyncEngine = engine) -> None:
    """Creates database tables asynchronously for migrations and integration test harnesses."""
    async with target_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
