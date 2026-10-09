Backend Architectural Logic
backend/models.py
This module utilizes SQLModel to unify database tables and Pydantic validation schemas.python from sqlmodel import SQLModel, Field, Relationship from pydantic import BaseModel from typing import Optional, List from datetime import datetime import uuid
class UserBase(SQLModel): email: str = Field(unique=True, index=True) age: int gender: str height_cm: float weight_kg: float body_fat_pct: Optional[float] = None free_text_goals: Optional[str] = None
class User(UserBase, table=True): id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True) hashed_password: str refresh_token_hash: Optional[str] = None workouts: List["WorkoutLog"] = Relationship(back_populates="user")
class WorkoutLog(SQLModel, table=True): id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True) user_id: uuid.UUID = Field(foreign_key="user.id") exercise_name: str weight_lifted: float repetitions: int estimated_1rm: float logged_at: datetime = Field(default_factory=datetime.utcnow) user: Optional[User] = Relationship(back_populates="workouts")
Pydantic AI Structured Output Schema
class RegimePlanResponse(BaseModel): target_calories_kcal: int target_protein_g: int training_split: List[str] exercise_selection: List[dict] # Contains exercise name, sets, and target RPE dietary_restrictions_noted: List[str]



## `backend/calculations.py`
This module isolates all domain-specific physiological mathematics.

```python
def calculate_tdee(user: UserBase, activity_multiplier: float = 1.55) -> float:
    """Calculates Total Daily Energy Expenditure using validated metabolic formulas."""
    if user.body_fat_pct:
        # Katch-McArdle Formula (Superior for known body composition)
        lean_body_mass = user.weight_kg * (1 - (user.body_fat_pct / 100))
        bmr = 370 + (21.6 * lean_body_mass)
    else:
        # Mifflin-St Jeor Equation (Standard for general populations)
        base = (10 * user.weight_kg) + (6.25 * user.height_cm) - (5 * user.age)
        bmr = base + 5 if user.gender.lower() == 'male' else base - 161
    
    return bmr * activity_multiplier

def calculate_composite_1rm(weight: float, reps: int) -> float:
    """Calculates an estimated 1RM using an average of Epley and Brzycki equations."""
    if reps == 1:
        return weight
    epley = weight * (1 + (reps / 30))
    brzycki = weight / (1.0278 - (0.0278 * reps))
    return (epley + brzycki) / 2


backend/agent.py
This module implements the Pydantic AI agent, enforcing strict schema compliance and managing retry budgets.



Python
from pydantic_ai import Agent, RunContext
from models import RegimePlanResponse, UserBase
import os

# Initialize the agent with strict typing and retry mechanisms
regime_agent = Agent(
    'openai:gpt-4o',
    result_type=RegimePlanResponse,
    retries=2, # Limits token burn on persistent validation failures
    system_prompt=(
        "You are an elite sports scientist and clinical nutritionist. "
        "Analyze the provided physical metrics and free-text goals to formulate a comprehensive regimen. "
        "CRITICAL RULES: "
        "- Do NOT invent exercises requiring specialized machinery if the user requests home workouts. "
        "- Always return caloric targets that align closely with the calculated TDEE. "
        "- Base protein targets on lean body mass parameters."
    )
)

async def generate_regimen(user: UserBase, calculated_tdee: float) -> RegimePlanResponse:
    prompt_context = (
        f"<user_profile>\n{user.model_dump_json()}\n</user_profile>\n"
        f"<metabolic_baseline>\nCalculated TDEE: {calculated_tdee} kcal\n</metabolic_baseline>\n"
        f"<goals>\n{user.free_text_goals}\n</goals>"
    )
    # The agent automatically retries upon Pydantic ValidationErrors
    result = await regime_agent.run(prompt_context)
    return result.data


backend/database.py
This module handles asynchronous connection pooling to prevent event loop blocking.



Python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/fitness_db")

# Pool size optimization to prevent exhaustion
engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=10)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session():
    """Dependency injection for route handlers ensuring transactions are safely closed."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise





### 3. `frontend.md`

This document details the structural logic of the Flet frontend, ensuring a cross-platform, responsive, and adaptive user experience.

# Frontend Architectural Logic

## `frontend/main.py`
The entry point manages routing, view stacks, and dynamic theme switching.python
import flet as ft
from views.login import login_view
from views.dashboard import dashboard_view
from views.settings import settings_view

def main(page: ft.Page):
    page.title = "AI Fitness Progression"
    # Adaptive theming based on OS settings
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed=ft.colors.INDIGO)
    
    def route_change(e):
        page.views.clear()
        if page.route == "/":
            page.views.append(login_view(page))
        elif page.route == "/dashboard":
            page.views.append(dashboard_view(page))
        elif page.route == "/settings":
            page.views.append(settings_view(page))
        page.update()

    def view_pop(e):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go("/")

# Target enables desktop rendering; Pyodide integration handles WebAssembly deployment
ft.app(target=main)


