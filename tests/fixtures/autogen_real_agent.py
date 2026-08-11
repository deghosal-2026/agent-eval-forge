"""Real AutoGen agent backed by local OMLX LLM for LLM-backed adapter tests."""

import os

from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

_INFO = ModelInfo(
    vision=False, function_calling=True,
    json_output=False, family="unknown", structured_output=False,
)


def build_agent(payload: dict | None = None) -> object:
    """Build a real AutoGen AssistantAgent using the local OMLX LLM."""
    mode = (payload or {}).get("context", {}).get("mode", "tool_call")
    model = os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit")
    base_url = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "omlx-test")

    client = OpenAIChatCompletionClient(
        model=model, base_url=base_url, api_key=api_key, model_info=_INFO,
    )

    if mode == "no_tool":
        return AssistantAgent(
            name="assistant", model_client=client,
            system_message="Answer concisely.",
        )
    return AssistantAgent(
        name="assistant",
        model_client=client,
        system_message="Answer concisely using tools when needed.",
        tools=[_weather_tool],
    )


async def _weather_tool(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to look up weather for.
    """
    if "london" in city.lower():
        return "The weather in London is 15C and sunny."
    return f"Weather data not available for {city}."
