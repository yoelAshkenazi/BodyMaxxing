"""User profile management router with strict Broken Object Level Authorization (BOLA) enforcement."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.database import get_async_session
from backend.models import User, UserRead, UserUpdateRequest
from backend.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Retrieve current user profile",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Returns the authenticated user's anthropometric profile.
    
    Guaranteed BOLA protection: Data is strictly scoped to the authenticated caller's identity.
    """
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update current user anthropometrics and fitness goals",
)
async def update_my_profile(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserRead:
    """Updates physical metrics and free-text goals with strict user-id scoping."""
    # BOLA Enforcement: Re-fetch using explicit user-id filter to ensure safe mutation within the transaction
    result = await session.execute(
        select(User).where(User.id == current_user.id)
    )
    user_to_update = result.scalar_one()

    update_data = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(user_to_update, field_name, value)

    session.add(user_to_update)
    return UserRead.model_validate(user_to_update)
