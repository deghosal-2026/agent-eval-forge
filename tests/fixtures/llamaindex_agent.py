"""Mock LlamaIndex agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock agent whose async
``.chat(user_msg=...)`` returns an ``AgentChatResponse`` mimicking
``llama_index.core.agent`` output. Modes are driven by payload context["mode"]:

- ``tool_call``: one tool source + final response
- ``no_tool``: final response only
- ``structured``: final response is a JSON dict (structured)
"""

import json
from types import SimpleNamespace


def _tool_output(name: str, raw_input: dict, raw_output: str) -> SimpleNamespace:
    return SimpleNamespace(
        tool_name=name,
        raw_input=raw_input,
        raw_output=raw_output,
        is_error=False,
        blocks=[],
    )


def build_agent(payload: dict) -> object:
    """Build a mock agent that returns a predefined AgentChatResponse per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")

    if mode == "no_tool":
        response = "I don't have enough information to answer."
        sources: list = []
    elif mode == "structured":
        response = json.dumps({"temperature": 15, "condition": "sunny"})
        sources = [_tool_output("get_weather", {"city": "London"}, '{"temp": 15}')]
    else:
        response = "The weather in London is 15\u00b0C."
        sources = [_tool_output("get_weather", {"city": "London"}, '{"temp": 15}')]

    result = SimpleNamespace(
        response=response,
        sources=sources,
        source_nodes=[],
        is_dummy_stream=False,
        metadata={},
    )

    async def chat(user_msg: str | None = None, **kwargs: object) -> object:
        return result

    return SimpleNamespace(chat=chat, name="llamaindex_mock_agent")
