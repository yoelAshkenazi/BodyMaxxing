"""Unit tests for domain physiological calculations and trendline modeling."""

from datetime import datetime, timedelta, timezone
import pytest

from backend.calculations import (
    calculate_composite_1rm,
    calculate_tdee,
    calculate_trendline,
)
from backend.models import UserBase


def test_calculate_tdee_mifflin_male() -> None:
    user = UserBase(
        email="male@test.com",
        age=25,
        gender="male",
        height_cm=180.0,
        weight_kg=80.0,
        body_fat_pct=None,
    )
    # BMR = (10*80) + (6.25*180) - (5*25) + 5 = 800 + 1125 - 125 + 5 = 1805
    # TDEE = 1805 * 1.55 = 2797.75
    tdee = calculate_tdee(user, activity_multiplier=1.55)
    assert tdee == 2797.75


def test_calculate_tdee_mifflin_female() -> None:
    user = UserBase(
        email="female@test.com",
        age=30,
        gender="female",
        height_cm=165.0,
        weight_kg=60.0,
        body_fat_pct=None,
    )
    # BMR = (10*60) + (6.25*165) - (5*30) - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
    # TDEE = 1320.25 * 1.2 = 1584.3
    tdee = calculate_tdee(user, activity_multiplier=1.2)
    assert tdee == 1584.3


def test_calculate_tdee_katch_mcardle() -> None:
    user = UserBase(
        email="athlete@test.com",
        age=28,
        gender="male",
        height_cm=175.0,
        weight_kg=80.0,
        body_fat_pct=15.0,
    )
    # LBM = 80 * (1 - 0.15) = 68.0 kg
    # BMR = 370 + (21.6 * 68) = 370 + 1468.8 = 1838.8
    # TDEE = 1838.8 * 1.55 = 2850.14
    tdee = calculate_tdee(user, activity_multiplier=1.55)
    assert tdee == 2850.14


def test_calculate_tdee_invalid_multiplier() -> None:
    user = UserBase(
        email="err@test.com",
        age=25,
        gender="male",
        height_cm=180.0,
        weight_kg=80.0,
    )
    with pytest.raises(ValueError, match="activity_multiplier must be strictly positive"):
        calculate_tdee(user, activity_multiplier=-1.0)


def test_calculate_composite_1rm_single_rep() -> None:
    # 1 rep equals the weight itself
    assert calculate_composite_1rm(100.0, 1) == 100.0


def test_calculate_composite_1rm_submaximal() -> None:
    # 100kg for 5 reps
    # Epley = 100 * (1 + 5/30) = 116.6666...
    # Brzycki = 100 / (1.0278 - (0.0278 * 5)) = 100 / 0.8888 = 112.511...
    # Composite avg ≈ 114.59
    val = calculate_composite_1rm(100.0, 5)
    assert 114.0 < val < 115.0


def test_calculate_composite_1rm_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="weight lifted must be strictly greater than 0"):
        calculate_composite_1rm(0.0, 5)

    with pytest.raises(ValueError, match="repetitions must be at least 1"):
        calculate_composite_1rm(100.0, 0)

    with pytest.raises(ValueError, match="exceed submaximal 1RM estimation validity"):
        calculate_composite_1rm(100.0, 40)


def test_calculate_trendline_empty_and_single() -> None:
    assert calculate_trendline([]) == {
        "current_1rm": 0.0,
        "slope_kg_per_week": 0.0,
        "forecast_4_weeks_1rm": 0.0,
    }

    now = datetime.now(timezone.utc)
    res = calculate_trendline([(now, 100.0)])
    assert res["current_1rm"] == 100.0
    assert res["slope_kg_per_week"] == 0.0
    assert res["forecast_4_weeks_1rm"] == 100.0


def test_calculate_trendline_progression() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = [
        (t0, 100.0),
        (t0 + timedelta(weeks=1), 102.5),
        (t0 + timedelta(weeks=2), 105.0),
        (t0 + timedelta(weeks=3), 107.5),
    ]
    res = calculate_trendline(points)
    assert res["current_1rm"] == 107.5
    assert pytest.approx(res["slope_kg_per_week"], 0.01) == 2.5
    # Forecast 4 weeks from current (107.5 + 4*2.5 = 117.5)
    assert pytest.approx(res["forecast_4_weeks_1rm"], 0.01) == 117.5


def test_calculate_trendline_identical_timestamps() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = [(t0, 100.0), (t0, 100.0)]
    res = calculate_trendline(points)
    assert res["slope_kg_per_week"] == 0.0
