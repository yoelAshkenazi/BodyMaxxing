"""Unit and integration tests for asynchronous database transactions and session pooling."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import select

from backend.database import (
    build_async_engine,
    get_async_session,
    get_session_context,
    init_db,
)
from backend.models import User


@pytest.fixture
async def test_async_engine():
    """In-memory async SQLite engine for deterministic testing."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)
    yield test_engine
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_build_async_engine() -> None:
    sqlite_eng = build_async_engine("sqlite+aiosqlite:///:memory:")
    assert sqlite_eng is not None
    await sqlite_eng.dispose()

    pg_eng = build_async_engine("postgresql+asyncpg://user:pass@localhost:5432/testdb")
    assert pg_eng is not None
    assert pg_eng.pool.size() == 20
    await pg_eng.dispose()


@pytest.mark.asyncio
async def test_session_commit_success(test_async_engine) -> None:
    session_factory = async_sessionmaker(
        bind=test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with get_session_context(session_factory) as session:
        user = User(
            email="commit_test@example.com",
            age=25,
            gender="male",
            height_cm=180.0,
            weight_kg=78.0,
            hashed_password="some_hashed_pass",
        )
        session.add(user)

    # Verify committed state in a separate session
    async with session_factory() as verify_session:
        result = await verify_session.execute(
            select(User).where(User.email == "commit_test@example.com")
        )
        saved_user = result.scalar_one_or_none()
        assert saved_user is not None
        assert saved_user.email == "commit_test@example.com"


@pytest.mark.asyncio
async def test_session_rollback_on_exception(test_async_engine) -> None:
    session_factory = async_sessionmaker(
        bind=test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    with pytest.raises(RuntimeError, match="Simulated crash"):
        async with get_session_context(session_factory) as session:
            user = User(
                email="rollback_test@example.com",
                age=25,
                gender="male",
                height_cm=180.0,
                weight_kg=78.0,
                hashed_password="some_hashed_pass",
            )
            session.add(user)
            raise RuntimeError("Simulated crash")

    # Verify transaction was rolled back
    async with session_factory() as verify_session:
        result = await verify_session.execute(
            select(User).where(User.email == "rollback_test@example.com")
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_async_session_dependency() -> None:
    gen = get_async_session()
    session = await anext(gen)
    assert isinstance(session, AsyncSession)
    # Complete generator
    try:
        await anext(gen)
    except StopAsyncIteration:
        pass
