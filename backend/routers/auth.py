"""Authentication router managing registration, credential verification, and refresh token rotation."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.database import get_async_session
from backend.models import (
    RefreshTokenRequest,
    TokenResponse,
    User,
    UserLoginRequest,
    UserRegisterRequest,
)
from backend.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
)
async def register(
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Creates a new user profile with Argon2-hashed password and returns JWT token pair."""
    normalized_email = payload.email.strip().lower()

    # Check for existing email registration
    result = await session.execute(
        select(User).where(User.email == normalized_email)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Hash user password
    hashed_pwd = hash_password(payload.password)

    user = User(
        email=normalized_email,
        hashed_password=hashed_pwd,
        age=payload.age,
        gender=payload.gender,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        body_fat_pct=payload.body_fat_pct,
        free_text_goals=payload.free_text_goals,
    )
    session.add(user)
    await session.flush()  # Populates user.id

    # Generate initial tokens
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)

    # Store hashed refresh token for rotation verification
    user.refresh_token_hash = hash_refresh_token(refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in_seconds=900,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and issue JWT pair",
)
async def login(
    payload: UserLoginRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Verifies Argon2 password and issues rotated access and refresh tokens."""
    normalized_email = payload.email.strip().lower()

    result = await session.execute(
        select(User).where(User.email == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)

    # Rotate refresh token hash in DB
    user.refresh_token_hash = hash_refresh_token(refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in_seconds=900,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new token pair",
)
async def refresh_token_endpoint(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Validates refresh token, detects replay attacks, and issues rotated tokens."""
    token_claims = decode_jwt_token(payload.refresh_token, expected_type="refresh")
    user_id_str = token_claims.get("sub")

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token claims",
        )

    user_id = uuid.UUID(user_id_str)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.refresh_token_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
        )

    # Verify against currently stored refresh token hash
    if not verify_refresh_token(payload.refresh_token, user.refresh_token_hash):
        # Potential token theft / reuse detected - immediately revoke token family
        user.refresh_token_hash = None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compromised refresh token detected. Session revoked.",
        )

    # Issue rotated token pair
    new_access_token = create_access_token(user_id=user.id, email=user.email)
    new_refresh_token = create_refresh_token(user_id=user.id)

    # Commit rotated hash
    user.refresh_token_hash = hash_refresh_token(new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in_seconds=900,
    )
