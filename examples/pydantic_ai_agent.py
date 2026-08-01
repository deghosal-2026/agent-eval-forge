"""Example PydanticAI agent for use with the PydanticAIAdapter.

Usage:
    uv run python examples/pydantic_ai_agent.py

To use with the adapter in a config:
    {"type": "pydantic-ai", "module": "examples.pydantic_ai_agent", "model": "..."}
"""

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent


@dataclass
class WeatherResult:
    temperature: float
    condition: str
    city: str


weather_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=WeatherResult,
    system_prompt="You are a helpful weather assistant.",
)


@weather_agent.tool_plain
def get_weather(city: str) -> dict[str, Any]:
    """Get the weather for a city."""
    return {"temperature": 15, "condition": "sunny", "city": city}


def build_agent(payload: dict[str, Any], model: str | None = None) -> Any:
    """Build a PydanticAI agent for the given scenario payload."""
    return weather_agent


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(weather_agent.run("What is the weather in London?"))
    print(f"Final: {result.data}")
    for msg in result.all_messages():
        print(f"Message: {msg}")
