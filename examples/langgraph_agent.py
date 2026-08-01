"""Example LangGraph agent for use with the LangGraphAdapter.

Usage:
    uv run python examples/langgraph_agent.py

To use with the adapter in a config:
    {"type": "langgraph", "module": "examples.langgraph_agent", "model": "..."}
"""

import json
from typing import Any

from langgraph.prebuilt import create_react_agent

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"],
        },
    },
]


def build_agent(payload: dict[str, Any], model: str | None = None) -> Any:
    """Build a prebuilt ReAct agent for the given scenario payload."""
    model_name = model or "openai:gpt-4o-mini"
    tools = payload.get("allowed_tools", TOOLS)
    agent = create_react_agent(model_name, tools=tools)
    return agent


if __name__ == "__main__":
    payload = {"input": "What is the weather in London?", "allowed_tools": TOOLS}
    agent = build_agent(payload)
    result = agent.invoke({"messages": [{"role": "user", "content": payload["input"]}]})
    for msg in result["messages"]:
        print(f"{msg.type}: {getattr(msg, 'content', '')}")