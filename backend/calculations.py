"""Domain-specific physiological mathematics and statistical trendline calculations."""

from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple
from backend.models import UserBase


def calculate_tdee(user: UserBase, activity_multiplier: float = 1.55) -> float:
    """Calculates Total Daily Energy Expenditure using validated metabolic formulas.
    
    If body fat percentage is provided, uses the Katch-McArdle Formula (more accurate
    for individuals with known body composition). Otherwise, defaults to the
    Mifflin-St Jeor Equation.
    """
    if activity_multiplier <= 0:
        raise ValueError("activity_multiplier must be strictly positive.")

    if user.body_fat_pct is not None and user.body_fat_pct > 0:
        # Katch-McArdle Formula
        lean_body_mass = user.weight_kg * (1.0 - (user.body_fat_pct / 100.0))
        bmr = 370.0 + (21.6 * lean_body_mass)
    else:
        # Mifflin-St Jeor Equation
        base = (10.0 * user.weight_kg) + (6.25 * user.height_cm) - (5.0 * user.age)
        bmr = base + 5.0 if user.gender.strip().lower() == "male" else base - 161.0

    return round(bmr * activity_multiplier, 2)


def calculate_composite_1rm(weight: float, reps: int) -> float:
    """Calculates estimated 1RM using an average of the Epley and Brzycki equations.
    
    For a single repetition (reps == 1), returns the exact weight lifted.
    Raises ValueError for invalid inputs (weight <= 0 or reps < 1 or reps >= 37 where Brzycki denominator <= 0).
    """
    if weight <= 0:
        raise ValueError("weight lifted must be strictly greater than 0.")
    if reps < 1:
        raise ValueError("repetitions must be at least 1.")
    if reps >= 37:
        raise ValueError("repetitions >= 37 exceed submaximal 1RM estimation validity.")

    if reps == 1:
        return float(weight)

    epley = weight * (1.0 + (reps / 30.0))
    brzycki = weight / (1.0278 - (0.0278 * reps))
    composite = (epley + brzycki) / 2.0

    return round(composite, 2)


def calculate_trendline(
    points: Sequence[Tuple[datetime, float]],
) -> Dict[str, float]:
    """Calculates least-squares linear regression over chronological (datetime, 1RM) points.
    
    Returns:
        dict containing:
            - current_1rm: latest observed 1RM
            - slope_kg_per_week: estimated rate of strength progression per week
            - forecast_4_weeks_1rm: forecasted 1RM in 4 weeks
    """
    if not points:
        return {
            "current_1rm": 0.0,
            "slope_kg_per_week": 0.0,
            "forecast_4_weeks_1rm": 0.0,
        }

    # Sort chronologically
    sorted_points = sorted(points, key=lambda p: p[0])
    current_1rm = sorted_points[-1][1]

    if len(sorted_points) == 1:
        return {
            "current_1rm": round(current_1rm, 2),
            "slope_kg_per_week": 0.0,
            "forecast_4_weeks_1rm": round(current_1rm, 2),
        }

    t0 = sorted_points[0][0].timestamp()
    # Convert seconds to weeks
    seconds_in_week = 7.0 * 24.0 * 3600.0

    x_vals = [(p[0].timestamp() - t0) / seconds_in_week for p in sorted_points]
    y_vals = [p[1] for p in sorted_points]

    n = len(x_vals)
    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xx = sum(x * x for x in x_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))

    denom = (n * sum_xx) - (sum_x * sum_x)
    if abs(denom) < 1e-9:
        slope = 0.0
    else:
        slope = ((n * sum_xy) - (sum_x * sum_y)) / denom

    # Slope is kg / week
    slope_kg_per_week = round(slope, 3)
    forecast_4_weeks = round(max(0.0, current_1rm + (slope_kg_per_week * 4.0)), 2)

    return {
        "current_1rm": round(current_1rm, 2),
        "slope_kg_per_week": slope_kg_per_week,
        "forecast_4_weeks_1rm": forecast_4_weeks,
    }
