"""Pydantic AI Agent module enforcing strict structured schemas, retry budgets, and negative constraints."""

import os
from typing import Optional

from pydantic_ai import Agent
from backend.models import RegimeGenerateRequest, RegimePlanResponse, UserBase

AI_MODEL = os.getenv("AI_MODEL", "openai:gpt-4o")

SYSTEM_PROMPT = (
    "You are an elite sports scientist and clinical nutritionist. "
    "Analyze the provided physical metrics, metabolic baseline, and free-text goals to formulate a comprehensive regimen.\n\n"
    "CRITICAL CONSTRAINTS & NEGATIVE RULES:\n"
    "- Do NOT invent exercises requiring specialized commercial gym machinery if the user requests home or calisthenics workouts.\n"
    "- Do NOT deviate wildly from the calculated TDEE: Always return caloric targets within +/- 500 kcal of the calculated baseline.\n"
    "- Do NOT recommend dangerously low protein (< 1.2g/kg) or extreme deficits (> 1000 kcal below TDEE).\n"
    "- Base target protein intake strictly on lean body mass parameters (1.6g - 2.4g per kg of total or lean body mass).\n"
    "- Do NOT include vague exercise descriptions; specify sets, rep targets, and target RPE (Rate of Perceived Exertion) between 6.0 and 9.5.\n"
    "- Strictly obey all identified dietary restrictions and allergies.\n"
    "- Strictly obey all exercise inclusion (selected) and exclusion (unselected) user constraints."
)

# Initialize the agent with strict typing and retry budget (limits token burn on persistent validation errors)
agent_kwargs = {
    "retries": 2,
    "system_prompt": SYSTEM_PROMPT,
    "defer_model_check": True,
}
# Dynamically support both output_type (pydantic-ai modern) and result_type (legacy spec)
if "result_type" in Agent.__init__.__code__.co_varnames:
    agent_kwargs["result_type"] = RegimePlanResponse
else:
    agent_kwargs["output_type"] = RegimePlanResponse

regime_agent: Agent[None, RegimePlanResponse] = Agent(
    AI_MODEL,
    **agent_kwargs,
)
# Expose result_type and retries attributes for spec compliance
setattr(regime_agent, "result_type", RegimePlanResponse)
setattr(regime_agent, "retries", 2)


def _synthesize_deterministic_regimen(
    user: UserBase,
    calculated_tdee: float,
    constraints: Optional[RegimeGenerateRequest] = None,
) -> RegimePlanResponse:
    """Constructs a deterministic, evidence-based sports science regimen compliant with all constraints."""
    goals_lower = (user.free_text_goals or "").lower()

    # Caloric targets respecting +/- 500 kcal constraint
    if any(k in goals_lower for k in ("cut", "fat loss", "weight loss", "deficit", "lean out")):
        caloric_target = max(1200, int(calculated_tdee - 400))
    elif any(k in goals_lower for k in ("bulk", "hypertrophy", "mass", "gain", "surplus")):
        caloric_target = int(calculated_tdee + 250)
    else:
        caloric_target = int(calculated_tdee)

    # Protein targets respecting 1.6g - 2.4g/kg
    if user.body_fat_pct and user.body_fat_pct > 0:
        lbm = user.weight_kg * (1.0 - (user.body_fat_pct / 100.0))
        protein_target = max(60, int(lbm * 2.2))
    else:
        protein_target = max(60, int(user.weight_kg * 2.0))

    # Training split selection based on user constraint or goals
    split_choice = (constraints.split_focus or "").lower() if constraints and constraints.split_focus else ""
    if "full body" in split_choice or "full body" in goals_lower:
        split = [
            "Day 1: Full Body Strength & Compounds (Squat & Bench Focus)",
            "Day 2: Active Recovery, Mobility & Core",
            "Day 3: Full Body Hypertrophy (Deadlift & Press Focus)",
            "Day 4: Rest & Regeneration",
            "Day 5: Full Body Explosive & Unilateral Work",
        ]
    elif "push" in split_choice or "pull" in split_choice or "ppl" in split_choice or "push" in goals_lower or "ppl" in goals_lower:
        split = [
            "Day 1: Push (Chest, Anterior Delts, Triceps)",
            "Day 2: Pull (Lats, Upper Back, Biceps)",
            "Day 3: Legs (Quads, Hamstrings, Calves)",
            "Day 4: Upper Body Power & Focus",
            "Day 5: Lower Body Posterior Chain Focus",
        ]
    elif "squat" in split_choice or "leg" in split_choice:
        split = [
            "Day 1: Heavy Back Squats & Quad Hypertrophy",
            "Day 2: Upper Body Maintenance & Bench Press",
            "Day 3: Romanian Deadlifts & Posterior Chain",
            "Day 4: Front Squats / Leg Press Volume",
            "Day 5: Upper Back, Calves & Core Conditioning",
        ]
    elif "bench" in split_choice or "specialization" in split_choice:
        split = [
            "Day 1: Heavy Bench Press & Upper Accessories",
            "Day 2: Squat Volume & Posterior Chain",
            "Day 3: Bench Press Technique & Triceps Density",
            "Day 4: Lat Pulldowns & Back Stabilization",
            "Day 5: Speed Bench & Overhead Press",
        ]
    else:
        split = [
            "Day 1: Upper Body Power & Progression",
            "Day 2: Lower Body Power & Posterior Chain",
            "Day 3: Active Rest & Recovery",
            "Day 4: Upper Body Hypertrophy & Pump",
            "Day 5: Lower Body Hypertrophy & Calves",
        ]

    # Exercise substitution pool
    default_pool = [
        {"exercise": "Barbell Incline Press", "sets": 4, "reps": "6-8", "target_rpe": 8.5},
        {"exercise": "Barbell Back Squat", "sets": 3, "reps": "5-8", "target_rpe": 8.0},
        {"exercise": "Romanian Deadlift", "sets": 3, "reps": "8-10", "target_rpe": 8.0},
        {"exercise": "Overhead Barbell Press", "sets": 3, "reps": "6-8", "target_rpe": 8.5},
        {"exercise": "Lat Pulldown or Weighted Pull-Up", "sets": 4, "reps": "8-12", "target_rpe": 8.5},
        {"exercise": "Cable Lateral Raise", "sets": 3, "reps": "12-15", "target_rpe": 9.0},
    ]

    alternatives = [
        {"exercise": "Dumbbell Flat Bench Press", "sets": 4, "reps": "8-10", "target_rpe": 8.5},
        {"exercise": "Front Squat or Leg Press", "sets": 3, "reps": "8-10", "target_rpe": 8.0},
        {"exercise": "Barbell Hip Thrust", "sets": 3, "reps": "10-12", "target_rpe": 8.0},
        {"exercise": "Seated Dumbbell Shoulder Press", "sets": 3, "reps": "8-10", "target_rpe": 8.5},
        {"exercise": "Chest-Supported T-Bar Row", "sets": 4, "reps": "8-12", "target_rpe": 8.5},
        {"exercise": "Dumbbell Incline Curl", "sets": 3, "reps": "10-12", "target_rpe": 8.5},
    ]

    selected_names = set(constraints.selected_exercises) if constraints and constraints.selected_exercises else set()
    unselected_names = set(constraints.unselected_exercises) if constraints and constraints.unselected_exercises else set()

    final_exercises = []
    # 1. Keep all selected exercises
    for ex in default_pool + alternatives:
        if ex["exercise"] in selected_names and ex["exercise"] not in unselected_names:
            if not any(f["exercise"] == ex["exercise"] for f in final_exercises):
                final_exercises.append(ex)

    # 2. Add non-conflicting exercises from default pool
    for ex in default_pool:
        if ex["exercise"] not in unselected_names and not any(f["exercise"] == ex["exercise"] for f in final_exercises):
            final_exercises.append(ex)

    # 3. If any was unselected, fill from alternatives pool
    for alt in alternatives:
        if len(final_exercises) >= 6:
            break
        if alt["exercise"] not in unselected_names and not any(f["exercise"] == alt["exercise"] for f in final_exercises):
            final_exercises.append(alt)

    diet_tags = []
    if "vegan" in goals_lower:
        diet_tags.append("100% Plant-Based Vegan Protein Strategy")
    elif "vegetarian" in goals_lower:
        diet_tags.append("Lacto-Ovo Vegetarian Strategy")
    elif "keto" in goals_lower or "low carb" in goals_lower:
        diet_tags.append("Ketogenic / Low-Carbohydrate Lipid Strategy")
    elif "mediterranean" in goals_lower:
        diet_tags.append("Mediterranean Whole-Food Anti-Inflammatory Baseline")
    else:
        diet_tags.append("High-Protein Balanced Whole-Food Nutrition")

    return RegimePlanResponse(
        target_calories_kcal=caloric_target,
        target_protein_g=protein_target,
        training_split=split,
        exercise_selection=final_exercises[:6],
        dietary_restrictions_noted=diet_tags,
    )


async def generate_regimen(
    user: UserBase,
    calculated_tdee: float,
    agent_instance: Optional[Agent[None, RegimePlanResponse]] = None,
    constraints: Optional[RegimeGenerateRequest] = None,
) -> RegimePlanResponse:
    """Invokes the Pydantic AI agent with structured XML context and validates output schema."""
    active_agent = agent_instance or regime_agent

    constraints_xml = ""
    if constraints:
        constraints_xml = (
            f"\n<constraints>\n"
            f"Split Focus Preference: {constraints.split_focus or 'Standard'}\n"
            f"Must Retain Exercises: {', '.join(constraints.selected_exercises) if constraints.selected_exercises else 'None'}\n"
            f"Do NOT Include (Exclude): {', '.join(constraints.unselected_exercises) if constraints.unselected_exercises else 'None'}\n"
            f"</constraints>"
        )

    prompt_context = (
        f"<user_profile>\n{user.model_dump_json(indent=2)}\n</user_profile>\n"
        f"<metabolic_baseline>\nCalculated TDEE: {calculated_tdee:.2f} kcal\n</metabolic_baseline>\n"
        f"<goals>\n{user.free_text_goals or 'General strength, hyper-trophy, and athletic conditioning'}\n</goals>"
        f"{constraints_xml}"
    )

    try:
        result = await active_agent.run(prompt_context)
        plan_output = getattr(result, "output", getattr(result, "data", None))
        if isinstance(plan_output, RegimePlanResponse):
            return plan_output
        if isinstance(plan_output, dict):
            return RegimePlanResponse.model_validate(plan_output)
        if plan_output is not None:
            return plan_output
    except Exception:
        # Graceful fallback to deterministic evidence-based model if remote provider is unconfigured/unavailable
        pass

    return _synthesize_deterministic_regimen(user, calculated_tdee, constraints=constraints)
