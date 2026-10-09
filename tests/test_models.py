"""Unit tests for models and Pydantic validation schemas."""

import uuid
import pytest
from pydantic import ValidationError

from backend.models import (
    RegimePlanResponse,
    User,
    UserBase,
    UserCreate,
    UserRegisterRequest,
    WorkoutLog,
    WorkoutLogCreate,
)


def test_user_base_validation() -> None:
    user = UserBase(
        email="test@domain.com",
        age=25,
        gender="male",
        height_cm=175.5,
        weight_kg=75.0,
        body_fat_pct=14.5,
        free_text_goals="Hypertrophy and strength",
    )
    assert user.email == "test@domain.com"
    assert user.age == 25
    assert user.height_cm == 175.5


def test_user_model_table_instantiation() -> None:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email="dbuser@test.com",
        age=30,
        gender="female",
        height_cm=165.0,
        weight_kg=60.0,
        hashed_password="argon2_hashed_secret",
    )
    assert user.id == uid
    assert user.hashed_password == "argon2_hashed_secret"
    assert user.refresh_token_hash is None


def test_workout_log_validation() -> None:
    uid = uuid.uuid4()
    log = WorkoutLog(
        user_id=uid,
        exercise_name="Barbell Bench Press",
        weight_lifted=100.0,
        repetitions=5,
        estimated_1rm=114.59,
    )
    assert log.exercise_name == "Barbell Bench Press"
    assert log.estimated_1rm == 114.59
    assert log.logged_at is not None


def test_regime_plan_response_schema() -> None:
    valid_data = {
        "target_calories_kcal": 2600,
        "target_protein_g": 175,
        "training_split": ["Push", "Pull", "Legs"],
        "exercise_selection": [
            {
                "exercise": "Incline Dumbbell Press",
                "sets": 3,
                "reps": "8-10",
                "target_rpe": 8.0,
            }
        ],
        "dietary_restrictions_noted": ["Lactose intolerant"],
    }
    plan = RegimePlanResponse.model_validate(valid_data)
    assert plan.target_calories_kcal == 2600
    assert plan.target_protein_g == 175
    assert len(plan.training_split) == 3


def test_regime_plan_response_extra_forbidden() -> None:
    invalid_data = {
        "target_calories_kcal": 2600,
        "target_protein_g": 175,
        "training_split": ["Push"],
        "exercise_selection": [],
        "dietary_restrictions_noted": [],
        "unexpected_field": "disallowed",
    }
    with pytest.raises(ValidationError):
        RegimePlanResponse.model_validate(invalid_data)


def test_user_register_request_validation() -> None:
    # Invalid password length
    with pytest.raises(ValidationError):
        UserRegisterRequest(
            email="valid@test.com",
            password="short",  # < 8 chars
            age=25,
            height_cm=180.0,
            weight_kg=80.0,
        )


def test_workout_log_create_validation() -> None:
    with pytest.raises(ValidationError):
        WorkoutLogCreate(
            exercise_name="Squat",
            weight_lifted=-50.0,  # <= 0 invalid
            repetitions=5,
        )
