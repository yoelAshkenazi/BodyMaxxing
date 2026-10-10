"""Unit and integration tests for Pydantic AI agent, prompt construction, and regime generation."""

import uuid
from fastapi import FastAPI, status
import httpx
from pydantic_ai.models.test import TestModel
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.agent import generate_regimen, regime_agent
from backend.database import get_async_session, init_db
from backend.models import RegimePlanResponse, User, UserBase
from backend.routers.regime import router as regime_router
from backend.security import create_access_token


SAMPLE_PLAN = {
    "target_calories_kcal": 2650,
    "target_protein_g": 185,
    "training_split": ["Upper Power", "Lower Power", "Upper Hypertrophy", "Lower Hypertrophy"],
    "exercise_selection": [
        {"exercise": "Barbell Incline Press", "sets": 4, "reps": "6-8", "target_rpe": 8.5},
        {"exercise": "Barbell Squat", "sets": 3, "reps": "5", "target_rpe": 8.0},
    ],
    "dietary_restrictions_noted": ["High-protein Mediterranean"],
}


def test_agent_configuration() -> None:
    """Verifies strict structured typing and retry budget constraints."""
    # Ensure structured output schema is enforced
    assert regime_agent.result_type == RegimePlanResponse
    # Enforce retry budget to mitigate token burn
    assert regime_agent.retries == 2


@pytest.mark.asyncio
async def test_generate_regimen_execution() -> None:
    user = UserBase(
        email="test_athlete@example.com",
        age=27,
        gender="male",
        height_cm=183.0,
        weight_kg=84.0,
        body_fat_pct=15.0,
        free_text_goals="Focus on hypertrophy and 1RM bench progression",
    )

    test_model = TestModel(custom_output_args=SAMPLE_PLAN)
    with regime_agent.override(model=test_model):
        plan = await generate_regimen(user, calculated_tdee=2800.0)

    assert isinstance(plan, RegimePlanResponse)
    assert plan.target_calories_kcal == 2650
    assert plan.target_protein_g == 185
    assert len(plan.training_split) == 4
    assert len(plan.exercise_selection) == 2


@pytest.fixture
async def regime_app_and_client():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    app = FastAPI()
    app.include_router(regime_router)

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
async def test_regime_api_endpoint(regime_app_and_client) -> None:
    client, session_factory = regime_app_and_client
    user_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email="ai_user@example.com",
                age=29,
                gender="female",
                height_cm=168.0,
                weight_kg=62.0,
                body_fat_pct=21.0,
                free_text_goals="Marathon endurance and core strength",
                hashed_password="hash",
            )
        )
        await session.commit()

    token = create_access_token(user_id=user_id, email="ai_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    test_model = TestModel(custom_output_args=SAMPLE_PLAN)
    with regime_agent.override(model=test_model):
        res = await client.post("/api/regime/generate", headers=headers)

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["target_calories_kcal"] == 2650
    assert data["target_protein_g"] == 185
    assert "Upper Power" in data["training_split"]


@pytest.mark.asyncio
async def test_regime_api_agent_failure(regime_app_and_client, monkeypatch) -> None:
    client, session_factory = regime_app_and_client
    user_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email="err_user@example.com",
                age=25,
                gender="male",
                height_cm=180.0,
                weight_kg=80.0,
                hashed_password="hash",
            )
        )
        await session.commit()

    token = create_access_token(user_id=user_id, email="err_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    async def mock_generate_regimen_fail(*args, **kwargs):
        raise RuntimeError("OpenAI rate limit exceeded")

    monkeypatch.setattr("backend.routers.regime.generate_regimen", mock_generate_regimen_fail)
    res = await client.post("/api/regime/generate", headers=headers)
    assert res.status_code == status.HTTP_502_BAD_GATEWAY
    assert "OpenAI rate limit exceeded" in res.json()["detail"]


@pytest.mark.asyncio
async def test_deterministic_regimen_constraints_split() -> None:
    from backend.agent import _synthesize_deterministic_regimen
    from backend.models import RegimeGenerateRequest

    user = UserBase(
        email="athlete@example.com",
        age=26,
        gender="male",
        height_cm=180.0,
        weight_kg=80.0,
        free_text_goals="Bench press power",
    )

    req_bench = RegimeGenerateRequest(
        split_focus="Bench Press Specialization",
        selected_exercises=["Barbell Incline Press"],
        unselected_exercises=["Barbell Back Squat"],
    )
    plan_bench = _synthesize_deterministic_regimen(user, calculated_tdee=2500.0, constraints=req_bench)
    assert any("Bench" in day for day in plan_bench.training_split)
    ex_names = [e["exercise"] for e in plan_bench.exercise_selection]
    assert "Barbell Incline Press" in ex_names
    assert "Barbell Back Squat" not in ex_names

    req_ppl = RegimeGenerateRequest(split_focus="Push / Pull / Legs (PPL)")
    plan_ppl = _synthesize_deterministic_regimen(user, calculated_tdee=2500.0, constraints=req_ppl)
    assert any("Push" in day for day in plan_ppl.training_split)

    req_legs = RegimeGenerateRequest(split_focus="Squat & Leg Hypertrophy")
    plan_legs = _synthesize_deterministic_regimen(user, calculated_tdee=2500.0, constraints=req_legs)
    assert any("Squat" in day for day in plan_legs.training_split)


@pytest.mark.asyncio
async def test_regime_api_endpoint_with_constraints(regime_app_and_client) -> None:
    client, session_factory = regime_app_and_client
    user_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email="split_user@example.com",
                age=24,
                gender="male",
                height_cm=175.0,
                weight_kg=75.0,
                hashed_password="hash",
            )
        )
        await session.commit()

    token = create_access_token(user_id=user_id, email="split_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "split_focus": "Push / Pull / Legs (PPL)",
        "selected_exercises": ["Barbell Incline Press"],
        "unselected_exercises": ["Barbell Back Squat"],
    }
    # Deterministic fallback execution without remote API key
    res = await client.post("/api/regime/generate", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "training_split" in data
    assert any("Push" in s for s in data["training_split"])
    ex_names = [e.get("exercise") for e in data["exercise_selection"]]
    assert "Barbell Incline Press" in ex_names
    assert "Barbell Back Squat" not in ex_names

