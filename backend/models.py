"""SQLModel and Pydantic schemas for database entities, API contracts, and AI agent output."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field as PydanticField
from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    """Core anthropometric and preference data attributes."""
    email: str = Field(unique=True, index=True, nullable=False)
    age: int = Field(gt=0, le=130)
    gender: str = Field(default="unspecified")
    height_cm: float = Field(gt=30.0, le=300.0)
    weight_kg: float = Field(gt=20.0, le=500.0)
    body_fat_pct: Optional[float] = Field(default=None, ge=1.0, le=75.0)
    free_text_goals: Optional[str] = Field(default=None, max_length=2000)


class User(UserBase, table=True):
    """Relational table model representing authenticated users."""
    __tablename__ = "user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    hashed_password: str = Field(nullable=False)
    refresh_token_hash: Optional[str] = Field(default=None)

    workouts: List["WorkoutLog"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class WorkoutLog(SQLModel, table=True):
    """Relational table model representing logged lifts and computed 1RM."""
    __tablename__ = "workout_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, nullable=False)
    exercise_name: str = Field(index=True, max_length=100)
    weight_lifted: float = Field(gt=0.0)
    repetitions: int = Field(gt=0, le=100)
    estimated_1rm: float = Field(gt=0.0)
    logged_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Optional[User] = Relationship(back_populates="workouts")


# -------------------------------------------------------------------------
# Pydantic AI Structured Output Schema
# -------------------------------------------------------------------------
class ExerciseDetail(BaseModel):
    """Specific prescription for an exercise."""
    name: str = PydanticField(..., description="Name of the prescribed exercise")
    sets: int = PydanticField(..., ge=1, le=20, description="Target working sets")
    reps: str = PydanticField(..., description="Repetition target or range (e.g. '8-12')")
    target_rpe: float = PydanticField(..., ge=5.0, le=10.0, description="Target Rate of Perceived Exertion (5-10)")
    notes: Optional[str] = PydanticField(default=None, description="Form cue or progression notes")


class RegimePlanResponse(BaseModel):
    """Guaranteed structured output contract for the Pydantic AI agent."""
    target_calories_kcal: int = PydanticField(..., gt=500, le=10000, description="Target daily caloric intake")
    target_protein_g: int = PydanticField(..., gt=20, le=500, description="Target daily protein intake in grams")
    training_split: List[str] = PydanticField(..., description="Days and focus, e.g. ['Push', 'Pull', 'Legs']")
    exercise_selection: List[Dict[str, Any]] = PydanticField(
        ...,
        description="List of selected exercises with sets, repetitions, and target RPE",
    )
    dietary_restrictions_noted: List[str] = PydanticField(
        default_factory=list,
        description="Identified allergies or dietary restrictions incorporated",
    )

    model_config = ConfigDict(extra="forbid")


class RegimeGenerateRequest(BaseModel):
    """Payload specifying user constraints and preferences for regimen generation/refinement."""
    split_focus: Optional[str] = PydanticField(
        default=None,
        description="Preferred split, e.g. Full Body, Push/Pull/Legs, Upper/Lower, Bench Specialization",
    )
    selected_exercises: List[str] = PydanticField(
        default_factory=list,
        description="Prescribed exercises the user wants to keep",
    )
    unselected_exercises: List[str] = PydanticField(
        default_factory=list,
        description="Prescribed exercises the user wants to replace with alternatives",
    )


# -------------------------------------------------------------------------
# Request / Response DTOs
# -------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    """Payload required to create a new user account."""
    email: EmailStr
    password: str = PydanticField(..., min_length=8, max_length=128)
    age: int = PydanticField(..., gt=0, le=130)
    gender: str = PydanticField(default="unspecified")
    height_cm: float = PydanticField(..., gt=30.0, le=300.0)
    weight_kg: float = PydanticField(..., gt=20.0, le=500.0)
    body_fat_pct: Optional[float] = PydanticField(default=None, ge=1.0, le=75.0)
    free_text_goals: Optional[str] = PydanticField(default=None, max_length=2000)


# Semantic alias
UserCreate = UserRegisterRequest


class UserLoginRequest(BaseModel):
    """Payload for password authentication."""
    email: EmailStr
    password: str


class UserUpdateRequest(BaseModel):
    """Payload for updating user profile and goals."""
    age: Optional[int] = PydanticField(default=None, gt=0, le=130)
    gender: Optional[str] = None
    height_cm: Optional[float] = PydanticField(default=None, gt=30.0, le=300.0)
    weight_kg: Optional[float] = PydanticField(default=None, gt=20.0, le=500.0)
    body_fat_pct: Optional[float] = PydanticField(default=None, ge=1.0, le=75.0)
    free_text_goals: Optional[str] = PydanticField(default=None, max_length=2000)


class UserRead(BaseModel):
    """Safe public representation of a user profile."""
    id: uuid.UUID
    email: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    body_fat_pct: Optional[float] = None
    free_text_goals: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """JWT bearer token response including refresh token."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 900  # 15 minutes


class RefreshTokenRequest(BaseModel):
    """Payload to exchange a refresh token for new tokens."""
    refresh_token: str


class WorkoutLogCreate(BaseModel):
    """Payload for recording a lift."""
    exercise_name: str = PydanticField(..., min_length=2, max_length=100)
    weight_lifted: float = PydanticField(..., gt=0.0)
    repetitions: int = PydanticField(..., ge=1, le=50)


class WorkoutLogRead(BaseModel):
    """Safe public representation of a workout log."""
    id: uuid.UUID
    user_id: uuid.UUID
    exercise_name: str
    weight_lifted: float
    repetitions: int
    estimated_1rm: float
    logged_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiftTrendPoint(BaseModel):
    """Data point in a 1RM historical progression."""
    logged_at: datetime
    estimated_1rm: float
    weight_lifted: float
    repetitions: int


class TrendForecastResponse(BaseModel):
    """Statistical regression and progress forecast for an exercise."""
    exercise_name: str
    data_points_count: int
    current_estimated_1rm: float
    slope_kg_per_week: float
    forecast_4_weeks_1rm: float
    history: List[LiftTrendPoint]
