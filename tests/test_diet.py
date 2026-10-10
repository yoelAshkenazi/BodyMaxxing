"""Unit and integration tests for diet calculations, meal style recipes, and diet API endpoints."""

import uuid
from fastapi import FastAPI, status
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.calculations import calculate_diet_macronutrients, generate_recipes_by_meal_style
from backend.database import get_async_session, init_db
from backend.models import User
from backend.routers.diet import router as diet_router
from backend.security import create_access_token


def test_calculate_diet_macronutrients() -> None:
    """Verifies BMR, TDEE, and macro distribution across deficit, maintenance, and surplus."""
    # Test deficit
    res_def = calculate_diet_macronutrients(
        weight_kg=80.0,
        height_cm=180.0,
        age=25,
        gender="male",
        body_fat_pct=14.0,
        activity_multiplier=1.55,
        goal="deficit",
    )
    assert res_def["target_calories"] < res_def["tdee"]
    assert res_def["protein_g"] >= 140
    assert res_def["fat_g"] >= 40
    assert res_def["carbs_g"] >= 50

    # Test surplus
    res_sur = calculate_diet_macronutrients(
        weight_kg=80.0,
        height_cm=180.0,
        age=25,
        gender="male",
        body_fat_pct=None,
        activity_multiplier=1.55,
        goal="surplus",
    )
    assert res_sur["target_calories"] > res_sur["tdee"]
    assert res_sur["protein_g"] == 160  # 80 * 2.0


def test_generate_recipes_by_meal_style() -> None:
    """Verifies meal breakdown, recipes, snacks, and drinks for 1_meal, 2_meals, and 3_meals."""
    # 1 Meal (OMAD)
    omad = generate_recipes_by_meal_style(2500, 160, 70, 300, meal_style="1_meal", include_snacks=True, include_drinks=True)
    assert omad["style_key"] == "1_meal"
    assert len(omad["meals"]) == 1
    assert len(omad["snacks"]) == 1
    assert len(omad["drinks"]) == 2
    assert "Ribeye" in omad["meals"][0]["recipe_title"]

    # 2 Meals (Intermittent Fasting 16:8)
    if_plan = generate_recipes_by_meal_style(2500, 160, 70, 300, meal_style="2_meals", include_snacks=True, include_drinks=True)
    assert if_plan["style_key"] == "2_meals"
    assert len(if_plan["meals"]) == 2
    assert len(if_plan["snacks"]) == 1

    # 3 Meals (Classic)
    classic = generate_recipes_by_meal_style(2500, 160, 70, 300, meal_style="3_meals", include_snacks=True, include_drinks=True)
    assert classic["style_key"] == "3_meals"
    assert len(classic["meals"]) == 3
    assert len(classic["snacks"]) == 1


@pytest.fixture
async def diet_app_and_client():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    app = FastAPI()
    app.include_router(diet_router)

    async def override_get_async_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_async_session

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, session_factory

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_diet_calculate_api_endpoint(diet_app_and_client) -> None:
    client, _ = diet_app_and_client
    payload = {
        "weight_kg": 85.0,
        "height_cm": 182.0,
        "age": 28,
        "gender": "male",
        "body_fat_pct": 15.0,
        "activity_multiplier": 1.55,
        "goal": "deficit",
        "meal_style": "2_meals",
        "include_snacks": True,
        "include_drinks": True,
    }
    res = await client.post("/api/diet/calculate", json=payload)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["style_key"] == "2_meals"
    assert len(data["meals"]) == 2
    assert data["target_calories"] > 1500
    assert data["protein_g"] >= 150
    assert len(data["snacks"]) == 1
    assert len(data["drinks"]) == 2


@pytest.mark.asyncio
async def test_my_diet_plan_authenticated_endpoint(diet_app_and_client) -> None:
    client, session_factory = diet_app_and_client
    user_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email="diet_athlete@example.com",
                age=26,
                gender="male",
                height_cm=185.0,
                weight_kg=88.0,
                body_fat_pct=13.0,
                free_text_goals="hypertrophy and strength",
                hashed_password="hash",
            )
        )
        await session.commit()

    token = create_access_token(user_id=user_id, email="diet_athlete@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/diet/me?meal_style=1_meal", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["style_key"] == "1_meal"
    assert len(data["meals"]) == 1
    assert data["protein_g"] >= 160
