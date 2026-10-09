"""Unit and integration tests for FastAPI application root, health checks, and SlowAPI limiter."""

from fastapi import Request, Response, status
import httpx
import pytest

from backend.main import app, limiter


@pytest.fixture
async def main_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_root_endpoint(main_client) -> None:
    res = await main_client.get("/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["name"] == "BodyMaxxing API"
    assert "/docs" in data["documentation"]


@pytest.mark.asyncio
async def test_health_endpoint(main_client) -> None:
    res = await main_client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_cors_headers(main_client) -> None:
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
    }
    res = await main_client.options("/api/auth/login", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_slowapi_rate_limiter_exceeded() -> None:
    # Test SlowAPI limiter manually to verify rate limit response
    @app.get("/test-limited")
    @limiter.limit("2/minute")
    async def limited_endpoint(request: Request, response: Response):
        return {"status": "ok"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r1 = await client.get("/test-limited")
        r2 = await client.get("/test-limited")
        r3 = await client.get("/test-limited")
        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK
        assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
