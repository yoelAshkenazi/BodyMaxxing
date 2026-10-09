"""Unit and integration tests for lift tracking, 1RM calculations, and BOLA protection."""

from datetime import datetime, timedelta, timezone
import uuid
from fastapi import FastAPI, status
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import get_async_session, init_db
from backend.models import User, WorkoutLog
from backend.routers.tracking import router as tracking_router
from backend.security import create_access_token


@pytest.fixture
async def tracking_app_and_client():
    """Builds a test application with an in-memory async SQLite engine."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    app = FastAPI()
    app.include_router(tracking_router)

    async def override_get_async_session():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_get_async_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, test_session_factory

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_lift_logging_and_history_with_bola(tracking_app_and_client) -> None:
    client, session_factory = tracking_app_and_client

    # Create two distinct users
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    async with session_factory() as session:
        user_a = User(
            id=user_a_id,
            email="usera@example.com",
            age=25,
            gender="male",
            height_cm=180.0,
            weight_kg=80.0,
            hashed_password="hash",
        )
        user_b = User(
            id=user_b_id,
            email="userb@example.com",
            age=30,
            gender="female",
            height_cm=165.0,
            weight_kg=60.0,
            hashed_password="hash",
        )
        session.add_all([user_a, user_b])
        await session.commit()

    token_a = create_access_token(user_id=user_a_id, email="usera@example.com")
    token_b = create_access_token(user_id=user_b_id, email="userb@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. User A logs a bench press lift
    log_payload = {
        "exercise_name": "Bench Press",
        "weight_lifted": 100.0,
        "repetitions": 5,
    }
    res_a = await client.post("/api/tracking/lifts", json=log_payload, headers=headers_a)
    assert res_a.status_code == status.HTTP_201_CREATED
    data_a = res_a.json()
    assert data_a["user_id"] == str(user_a_id)
    assert data_a["exercise_name"] == "Bench Press"
    assert 114.0 < data_a["estimated_1rm"] < 115.0
    lift_a_id = data_a["id"]

    # 2. User B logs a squat lift
    res_b = await client.post(
        "/api/tracking/lifts",
        json={"exercise_name": "Back Squat", "weight_lifted": 140.0, "repetitions": 3},
        headers=headers_b,
    )
    assert res_b.status_code == status.HTTP_201_CREATED
    data_b = res_b.json()
    assert data_b["user_id"] == str(user_b_id)

    # 3. BOLA Verification: User A retrieves history, must NOT see User B's squat
    hist_a = await client.get("/api/tracking/history", headers=headers_a)
    assert hist_a.status_code == status.HTTP_200_OK
    items_a = hist_a.json()
    assert len(items_a) == 1
    assert items_a[0]["exercise_name"] == "Bench Press"

    # User B retrieves history, must NOT see User A's bench press
    hist_b = await client.get("/api/tracking/history", headers=headers_b)
    assert hist_b.status_code == status.HTTP_200_OK
    items_b = hist_b.json()
    assert len(items_b) == 1
    assert items_b[0]["exercise_name"] == "Back Squat"

    # 4. Filter by exercise name
    filtered = await client.get("/api/tracking/history?exercise_name=bench", headers=headers_a)
    assert filtered.status_code == status.HTTP_200_OK
    assert len(filtered.json()) == 1

    empty_filter = await client.get("/api/tracking/history?exercise_name=deadlift", headers=headers_a)
    assert empty_filter.status_code == status.HTTP_200_OK
    assert len(empty_filter.json()) == 0

    # 5. BOLA Deletion Check: User B attempts to delete User A's lift -> 404
    del_attempt = await client.delete(f"/api/tracking/lifts/{lift_a_id}", headers=headers_b)
    assert del_attempt.status_code == status.HTTP_404_NOT_FOUND

    # User A successfully deletes own lift
    del_success = await client.delete(f"/api/tracking/lifts/{lift_a_id}", headers=headers_a)
    assert del_success.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_lift_logging_validation_errors(tracking_app_and_client) -> None:
    client, session_factory = tracking_app_and_client
    user_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email="val@example.com",
                age=25,
                gender="male",
                height_cm=180.0,
                weight_kg=80.0,
                hashed_password="hash",
            )
        )
        await session.commit()
    token = create_access_token(user_id=user_id, email="val@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Blank exercise name
    res = await client.post(
        "/api/tracking/lifts",
        json={"exercise_name": "   ", "weight_lifted": 100.0, "repetitions": 5},
        headers=headers,
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Invalid repetitions (e.g. 40 reps exceeds composite limit)
    res_reps = await client.post(
        "/api/tracking/lifts",
        json={"exercise_name": "Bench Press", "weight_lifted": 100.0, "repetitions": 40},
        headers=headers,
    )
    assert res_reps.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_strength_forecast_endpoint(tracking_app_and_client) -> None:
    client, session_factory = tracking_app_and_client
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, email="forecast@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Seed chronological lifts
    t0 = datetime.now(timezone.utc) - timedelta(weeks=3)
    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email="forecast@example.com",
                age=25,
                gender="male",
                height_cm=180.0,
                weight_kg=80.0,
                hashed_password="hash",
            )
        )
        session.add_all([
            WorkoutLog(
                user_id=user_id,
                exercise_name="Overhead Press",
                weight_lifted=50.0,
                repetitions=5,
                estimated_1rm=57.3,
                logged_at=t0,
            ),
            WorkoutLog(
                user_id=user_id,
                exercise_name="Overhead Press",
                weight_lifted=52.5,
                repetitions=5,
                estimated_1rm=60.1,
                logged_at=t0 + timedelta(weeks=1),
            ),
            WorkoutLog(
                user_id=user_id,
                exercise_name="Overhead Press",
                weight_lifted=55.0,
                repetitions=5,
                estimated_1rm=63.0,
                logged_at=t0 + timedelta(weeks=2),
            ),
        ])
        await session.commit()

    res = await client.get("/api/tracking/forecast?exercise_name=Overhead Press", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    forecast_data = res.json()
    assert forecast_data["exercise_name"] == "Overhead Press"
    assert forecast_data["data_points_count"] == 3
    assert forecast_data["current_estimated_1rm"] == 63.0
    assert forecast_data["slope_kg_per_week"] > 0
    assert forecast_data["forecast_4_weeks_1rm"] > forecast_data["current_estimated_1rm"]
