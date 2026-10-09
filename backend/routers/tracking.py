"""Tracking router for logging submaximal lifts, historical queries, and strength progression trendlines."""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, desc, select

from backend.calculations import calculate_composite_1rm, calculate_trendline
from backend.database import get_async_session
from backend.models import (
    LiftTrendPoint,
    TrendForecastResponse,
    User,
    WorkoutLog,
    WorkoutLogCreate,
    WorkoutLogRead,
)
from backend.security import get_current_user

router = APIRouter(prefix="/api/tracking", tags=["Strength Tracking"])


@router.post(
    "/lifts",
    response_model=WorkoutLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a submaximal lift and calculate estimated 1RM",
)
async def log_lift(
    payload: WorkoutLogCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> WorkoutLogRead:
    """Calculates composite 1RM (Epley + Brzycki) and stores lift scoped to authenticated user."""
    clean_exercise_name = payload.exercise_name.strip()
    if not clean_exercise_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exercise name cannot be blank",
        )

    try:
        estimated_1rm = calculate_composite_1rm(payload.weight_lifted, payload.repetitions)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    # BOLA Enforcement: user_id is derived strictly from authenticated JWT identity
    workout = WorkoutLog(
        user_id=current_user.id,
        exercise_name=clean_exercise_name,
        weight_lifted=payload.weight_lifted,
        repetitions=payload.repetitions,
        estimated_1rm=estimated_1rm,
    )
    session.add(workout)
    await session.flush()

    return WorkoutLogRead.model_validate(workout)


@router.get(
    "/history",
    response_model=List[WorkoutLogRead],
    summary="Retrieve workout log history with BOLA enforcement",
)
async def get_workout_history(
    exercise_name: Optional[str] = Query(default=None, description="Filter by exercise name"),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[WorkoutLogRead]:
    """Retrieves workout logs strictly belonging to the authenticated caller."""
    query = select(WorkoutLog).where(WorkoutLog.user_id == current_user.id)

    if exercise_name:
        query = query.where(col(WorkoutLog.exercise_name).ilike(f"%{exercise_name.strip()}%"))

    query = query.order_by(desc(WorkoutLog.logged_at)).limit(limit)

    result = await session.execute(query)
    logs = result.scalars().all()
    return [WorkoutLogRead.model_validate(log) for log in logs]


@router.get(
    "/forecast",
    response_model=TrendForecastResponse,
    summary="Generate statistical regression trendline and 4-week forecast for an exercise",
)
async def get_strength_forecast(
    exercise_name: str = Query(..., min_length=2, description="Exercise name to analyze"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> TrendForecastResponse:
    """Computes rate of progression (kg/week) and 4-week forecast using least-squares regression."""
    clean_exercise_name = exercise_name.strip()

    # BOLA Enforcement: Only load records belonging to the current user
    query = (
        select(WorkoutLog)
        .where(
            WorkoutLog.user_id == current_user.id,
            col(WorkoutLog.exercise_name).ilike(clean_exercise_name),
        )
        .order_by(WorkoutLog.logged_at.asc())
    )

    result = await session.execute(query)
    logs = result.scalars().all()

    points = [(log.logged_at, log.estimated_1rm) for log in logs]
    trend_stats = calculate_trendline(points)

    history_points = [
        LiftTrendPoint(
            logged_at=log.logged_at,
            estimated_1rm=log.estimated_1rm,
            weight_lifted=log.weight_lifted,
            repetitions=log.repetitions,
        )
        for log in logs
    ]

    return TrendForecastResponse(
        exercise_name=clean_exercise_name,
        data_points_count=len(history_points),
        current_estimated_1rm=trend_stats["current_1rm"],
        slope_kg_per_week=trend_stats["slope_kg_per_week"],
        forecast_4_weeks_1rm=trend_stats["forecast_4_weeks_1rm"],
        history=history_points,
    )


@router.delete(
    "/lifts/{lift_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a logged lift with BOLA ownership validation",
)
async def delete_lift(
    lift_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Deletes a lift only if it belongs to the authenticated user."""
    result = await session.execute(
        select(WorkoutLog).where(
            WorkoutLog.id == lift_id,
            WorkoutLog.user_id == current_user.id,
        )
    )
    lift = result.scalar_one_or_none()
    if lift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lift record not found or unauthorized",
        )

    await session.delete(lift)
