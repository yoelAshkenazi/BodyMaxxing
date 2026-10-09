"""Unit and integration tests for authentication, Argon2 hashing, JWT tokens, and BOLA security."""

from datetime import timedelta
import uuid
from fastapi import FastAPI, HTTPException, status
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import select

from backend.database import get_async_session, init_db
from backend.models import User
from backend.routers.auth import router as auth_router
from backend.routers.users import router as users_router
from backend.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)


@pytest.fixture
async def app_and_client():
    """Builds a test FastAPI application with an in-memory async database."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(users_router)

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


def test_argon2_hashing() -> None:
    raw = "SuperSecretPassword123!"
    hashed = hash_password(raw)
    assert hashed.startswith("$argon2")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password(raw, "invalid_hash") is False


def test_refresh_token_hashing() -> None:
    token = "sample_refresh_token_string"
    hashed = hash_refresh_token(token)
    assert verify_refresh_token(token, hashed) is True
    assert verify_refresh_token("altered_token", hashed) is False


def test_jwt_generation_and_decode() -> None:
    uid = uuid.uuid4()
    access = create_access_token(user_id=uid, email="user@example.com")
    payload = decode_jwt_token(access, expected_type="access")
    assert payload["sub"] == str(uid)
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "access"

    refresh = create_refresh_token(user_id=uid)
    refresh_payload = decode_jwt_token(refresh, expected_type="refresh")
    assert refresh_payload["sub"] == str(uid)
    assert refresh_payload["type"] == "refresh"


def test_jwt_expired() -> None:
    uid = uuid.uuid4()
    expired_token = create_access_token(
        user_id=uid,
        email="expired@example.com",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_jwt_token(expired_token)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_jwt_invalid_type_and_malformed() -> None:
    uid = uuid.uuid4()
    access_token = create_access_token(user_id=uid, email="user@example.com")
    with pytest.raises(HTTPException) as exc_info:
        decode_jwt_token(access_token, expected_type="refresh")
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    with pytest.raises(HTTPException) as exc_malformed:
        decode_jwt_token("not.a.valid.jwt")
    assert exc_malformed.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow(app_and_client) -> None:
    client, _ = app_and_client

    # 1. Register new user
    reg_payload = {
        "email": "athlete@example.com",
        "password": "StrongPassword123!",
        "age": 28,
        "gender": "male",
        "height_cm": 182.0,
        "weight_kg": 85.0,
        "body_fat_pct": 14.0,
        "free_text_goals": "Build muscle and increase squat",
    }
    reg_res = await client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == status.HTTP_201_CREATED
    data = reg_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 2. Duplicate registration rejected
    dup_res = await client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == status.HTTP_409_CONFLICT

    # 3. Successful login
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "athlete@example.com", "password": "StrongPassword123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    new_tokens = login_res.json()
    assert "access_token" in new_tokens

    # 4. Failed login
    bad_login = await client.post(
        "/api/auth/login",
        json={"email": "athlete@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == status.HTTP_401_UNAUTHORIZED

    # 5. Access protected /api/users/me with BOLA check
    headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
    me_res = await client.get("/api/users/me", headers=headers)
    assert me_res.status_code == status.HTTP_200_OK
    user_info = me_res.json()
    assert user_info["email"] == "athlete@example.com"
    assert user_info["weight_kg"] == 85.0

    # 6. Update profile
    patch_res = await client.patch(
        "/api/users/me",
        json={"weight_kg": 86.5, "body_fat_pct": 13.5},
        headers=headers,
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["weight_kg"] == 86.5
    assert patch_res.json()["body_fat_pct"] == 13.5

    # 7. Refresh token rotation
    refresh_res = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert refresh_res.status_code == status.HTTP_200_OK
    rotated = refresh_res.json()
    assert rotated["access_token"] != new_tokens["access_token"]
    assert rotated["refresh_token"] != new_tokens["refresh_token"]

    # 8. Reusing old refresh token must be rejected (replay attack mitigation)
    replay_res = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert replay_res.status_code == status.HTTP_401_UNAUTHORIZED
