"""Pydantic AI Agent module enforcing strict structured schemas, retry budgets, and negative constraints."""

import os
from typing import Optional

from pydantic_ai import Agent
from backend.models import RegimePlanResponse, UserBase

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
    "- Strictly obey all identified dietary restrictions and allergies."
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


async def generate_regimen(
    user: UserBase,
    calculated_tdee: float,
    agent_instance: Optional[Agent[None, RegimePlanResponse]] = None,
) -> RegimePlanResponse:
    """Invokes the Pydantic AI agent with structured XML context and validates output schema."""
    active_agent = agent_instance or regime_agent

    prompt_context = (
        f"<user_profile>\n{user.model_dump_json(indent=2)}\n</user_profile>\n"
        f"<metabolic_baseline>\nCalculated TDEE: {calculated_tdee:.2f} kcal\n</metabolic_baseline>\n"
        f"<goals>\n{user.free_text_goals or 'General strength, hyper-trophy, and athletic conditioning'}\n</goals>"
    )

    result = await active_agent.run(prompt_context)
    plan_output = getattr(result, "output", getattr(result, "data", None))
    if isinstance(plan_output, RegimePlanResponse):
        return plan_output
    if isinstance(plan_output, dict):
        return RegimePlanResponse.model_validate(plan_output)
    return plan_output
