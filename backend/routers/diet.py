"""Diet router providing personalized macronutrient calculations and recipe recommendations."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from backend.calculations import calculate_diet_macronutrients, generate_recipes_by_meal_style
from backend.models import User
from backend.security import get_current_user

router = APIRouter(prefix="/api/diet", tags=["Diet & Nutritional Planning"])


class DietCalculateRequest(BaseModel):
    weight_kg: float = Field(..., gt=20.0, le=500.0)
    height_cm: float = Field(..., gt=50.0, le=300.0)
    age: int = Field(..., gt=10, le=120)
    gender: str = Field(default="male")
    body_fat_pct: Optional[float] = Field(default=None, ge=1.0, le=75.0)
    activity_multiplier: float = Field(default=1.55, ge=1.1, le=2.5)
    goal: str = Field(default="maintenance")
    meal_style: str = Field(default="3_meals")
    include_snacks: bool = Field(default=True)
    include_drinks: bool = Field(default=True)


class DietPlanResponse(BaseModel):
    bmr: float
    tdee: float
    target_calories: int
    protein_g: int
    fat_g: int
    carbs_g: int
    goal_label: str
    style_key: str
    style_title: str
    meals: List[Dict[str, Any]]
    snacks: List[Dict[str, Any]]
    drinks: List[Dict[str, Any]]


@router.post(
    "/calculate",
    response_model=DietPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate macronutrient targets and meal recipes for custom parameters",
)
async def calculate_custom_diet_plan(payload: DietCalculateRequest) -> DietPlanResponse:
    """Calculates ideal calories/protein/fat/carbs and generates suggested recipes based on meal style."""
    macros = calculate_diet_macronutrients(
        weight_kg=payload.weight_kg,
        height_cm=payload.height_cm,
        age=payload.age,
        gender=payload.gender,
        body_fat_pct=payload.body_fat_pct,
        activity_multiplier=payload.activity_multiplier,
        goal=payload.goal,
    )

    plan = generate_recipes_by_meal_style(
        target_calories=macros["target_calories"],
        target_protein_g=macros["protein_g"],
        target_fat_g=macros["fat_g"],
        target_carbs_g=macros["carbs_g"],
        meal_style=payload.meal_style,
        include_snacks=payload.include_snacks,
        include_drinks=payload.include_drinks,
    )

    return DietPlanResponse(
        bmr=macros["bmr"],
        tdee=macros["tdee"],
        target_calories=macros["target_calories"],
        protein_g=macros["protein_g"],
        fat_g=macros["fat_g"],
        carbs_g=macros["carbs_g"],
        goal_label=macros["goal_label"],
        style_key=plan["style_key"],
        style_title=plan["style_title"],
        meals=plan["meals"],
        snacks=plan["snacks"],
        drinks=plan["drinks"],
    )


@router.get(
    "/me",
    response_model=DietPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get personalized diet plan derived from authenticated user's physical profile",
)
async def get_my_diet_plan(
    meal_style: str = Query("3_meals", description="1_meal, 2_meals, or 3_meals"),
    goal: str = Query("maintenance", description="deficit, surplus, or maintenance"),
    include_snacks: bool = Query(True),
    include_drinks: bool = Query(True),
    current_user: User = Depends(get_current_user),
) -> DietPlanResponse:
    """Generates personalized diet plan from current user's profile and requested meal style."""
    user_goal = goal
    if user_goal == "maintenance" and current_user.free_text_goals:
        user_goal = current_user.free_text_goals

    macros = calculate_diet_macronutrients(
        weight_kg=current_user.weight_kg,
        height_cm=current_user.height_cm,
        age=current_user.age,
        gender=current_user.gender,
        body_fat_pct=current_user.body_fat_pct,
        activity_multiplier=1.55,
        goal=user_goal,
    )

    plan = generate_recipes_by_meal_style(
        target_calories=macros["target_calories"],
        target_protein_g=macros["protein_g"],
        target_fat_g=macros["fat_g"],
        target_carbs_g=macros["carbs_g"],
        meal_style=meal_style,
        include_snacks=include_snacks,
        include_drinks=include_drinks,
    )

    return DietPlanResponse(
        bmr=macros["bmr"],
        tdee=macros["tdee"],
        target_calories=macros["target_calories"],
        protein_g=macros["protein_g"],
        fat_g=macros["fat_g"],
        carbs_g=macros["carbs_g"],
        goal_label=macros["goal_label"],
        style_key=plan["style_key"],
        style_title=plan["style_title"],
        meals=plan["meals"],
        snacks=plan["snacks"],
        drinks=plan["drinks"],
    )
