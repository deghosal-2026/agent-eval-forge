"""Mock OpenAI Agents SDK agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock agent whose
``.run_sync(input)`` returns a RunResult mimicking ``agents.Runner.run_sync``
output. Modes driven by payload context["mode"]:

- ``tool_call``: tool call + tool result + final response
- ``no_tool``: final response only
- ``structured``: structured output (final_output as dict)
"""

from types import SimpleNamespace


def _item(type_: str, **kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(type=type_, **kwargs)


def _usage() -> SimpleNamespace:
    return SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)


def build_agent(payload: dict) -> object:
    """Build a mock agent that returns a predefined RunResult per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")

    if mode == "no_tool":
        final_output = "I have no tools available."
        items = [_item("message", text=final_output)]
    elif mode == "structured":
        final_output = {"temperature": 15, "condition": "sunny"}
        items = [
            _item(
                "function_call",
                raw_item=SimpleNamespace(name="get_weather", arguments='{"city": "London"}'),
            ),
            _item(
                "function_call_output",
                raw_item=SimpleNamespace(name="get_weather", output='{"temp": 15}'),
            ),
            _item("message", text=str(final_output)),
        ]
    else:
        final_output = "The weather in London is 15\u00b0C."
        items = [
            _item(
                "function_call",
                raw_item=SimpleNamespace(name="get_weather", arguments='{"city": "London"}'),
            ),
            _item(
                "function_call_output",
                raw_item=SimpleNamespace(name="get_weather", output='{"temp": 15}'),
            ),
            _item("message", text=final_output),
        ]

    result = SimpleNamespace(final_output=final_output, new_items=items, usage=_usage())
    return SimpleNamespace(run_sync=lambda input_str: result, name="openai_agents_mock_agent")
