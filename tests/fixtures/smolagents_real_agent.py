"""Real smolagents agent backed by local OMLX LLM for LLM-backed adapter tests."""

import os

from smolagents import CodeAgent, LiteLLMModel, tool


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to look up weather for.

    Returns:
        A string describing the weather conditions.
    """
    if "london" in city.lower():
        return "The weather in London is 15C and sunny."
    return f"Weather data not available for {city}."


def build_agent(payload: dict | None = None) -> CodeAgent:
    """Build a real smolagents CodeAgent using the local OMLX LLM."""
    model = LiteLLMModel(
        model_id="openai/" + os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit"),
        api_base=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "omlx-test"),
    )
    return CodeAgent(tools=[get_weather], model=model)
