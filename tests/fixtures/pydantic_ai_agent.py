"""Mock PydanticAI agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock agent whose
``.run_sync(input)`` returns a result mimicking ``pydantic_ai.Agent`` output.
Modes driven by payload context["mode"]:

- ``tool_call``: one tool call + result + final response
- ``no_tool``: final response only
- ``structured``: returns structured data (dict) as result.data
"""

from types import SimpleNamespace


def _part(kind: str, **kwargs: object) -> SimpleNamespace:
    ns = SimpleNamespace(**kwargs)
    ns.kind = lambda: kind
    return ns


def build_agent(payload: dict) -> object:
    mode = payload.get("context", {}).get("mode", "tool_call")
    user_input = payload.get("input", "")

    if mode == "no_tool":
        data = "I have no tools available."
        messages = [SimpleNamespace(
            parts=[_part("final", content=data)],
            role="assistant",
        )]
    elif mode == "structured":
        data = {"temperature": 15, "condition": "sunny"}
        messages = [
            SimpleNamespace(
                parts=[_part("tool-call", tool_name="get_weather",
                             args={"city": "London"})],
                role="assistant",
            ),
            SimpleNamespace(
                parts=[_part("tool-return", tool_name="get_weather",
                             content={"temp": 15})],
                role="tool",
            ),
            SimpleNamespace(
                parts=[_part("final", content=str(data))],
                role="assistant",
            ),
        ]
    else:
        data = "The weather in London is 15\u00b0C."
        messages = [
            SimpleNamespace(
                parts=[_part("tool-call", tool_name="get_weather",
                             args={"city": "London"})],
                role="assistant",
            ),
            SimpleNamespace(
                parts=[_part("tool-return", tool_name="get_weather",
                             content={"temp": 15})],
                role="tool",
            ),
            SimpleNamespace(
                parts=[_part("final", content=data)],
                role="assistant",
            ),
        ]

    result = SimpleNamespace(all_messages=lambda: messages, data=data)
    return SimpleNamespace(run_sync=lambda input_str: result, name="pydanticai_mock")