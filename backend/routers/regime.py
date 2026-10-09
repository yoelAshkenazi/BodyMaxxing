"""Regime planning router invoking the Pydantic AI agent for personalized nutrition and workouts."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.agent import generate_regimen
from backend.calculations import calculate_tdee
from backend.models import RegimePlanResponse, User
from backend.security import get_current_user

router = APIRouter(prefix="/api/regime", tags=["AI Regime Generation"])


@router.post(
    "/generate",
    response_model=RegimePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate personalized nutritional and training regimen using Pydantic AI",
)
async def generate_user_regimen(
    current_user: User = Depends(get_current_user),
) -> RegimePlanResponse:
    """Computes metabolic expenditure and invokes Pydantic AI agent to construct structured plan."""
    try:
        calculated_tdee = calculate_tdee(current_user)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to calculate TDEE from user metrics: {err}",
        )

    try:
        regime = await generate_regimen(current_user, calculated_tdee)
        return regime
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Agent generation failure: {err}",
        )
