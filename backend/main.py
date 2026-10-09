"""FastAPI application entry point configuring CORS, SlowAPI rate limiting, and async API routers."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.database import engine, init_db
from backend.routers import auth, regime, tracking, users

# SlowAPI Rate Limiter Initialization
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    headers_enabled=True,
    storage_uri="memory://",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle: initializes schemas on startup."""
    # Run lightweight schema initialization if running in development / test mode
    if os.getenv("ENVIRONMENT", "development") != "production":
        await init_db(engine)
    yield
    # Clean shutdown of database pool connections
    await engine.dispose()


app = FastAPI(
    title="BodyMaxxing API",
    description="Production-grade asynchronous API for health, strength tracking, and AI regime generation.",
    version="0.1.0",
    lifespan=lifespan,
)

# Attach rate limiter state and middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS Configuration
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000,http://localhost:8550,http://127.0.0.1:8550",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tracking.router)
app.include_router(regime.router)


@app.get("/health", tags=["System"], summary="API Health Check")
async def health_check() -> JSONResponse:
    """Returns application health status, active environment, and timestamp."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.1.0",
        },
    )


@app.get("/", tags=["System"], summary="Root Information")
async def root() -> JSONResponse:
    """Root metadata providing API documentation references."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "name": "BodyMaxxing API",
            "documentation": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
        },
    )
