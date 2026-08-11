"""Mock Google ADK agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock runner whose
``.run(*, user_id, session_id, new_message)`` yields ``Event`` objects mimicking
``google.adk`` output. Modes are driven by payload context["mode"]:

- ``tool_call``: a function-call event + function-response event + final event
- ``no_tool``: final event only
- ``structured``: final event text is a JSON dict (structured)
"""

import json
from types import SimpleNamespace


def _function_call(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(id="call_1", name=name, args=args)


def _function_response(name: str, response: object) -> SimpleNamespace:
    return SimpleNamespace(id="call_1", name=name, response=response)


def _content(text: str) -> SimpleNamespace:
    return SimpleNamespace(parts=[SimpleNamespace(text=text)])


def _event(
    *,
    calls: list | None = None,
    responses: list | None = None,
    is_final: bool = False,
    content: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        get_function_calls=lambda: calls or [],
        get_function_responses=lambda: responses or [],
        is_final_response=lambda: is_final,
        content=content,
        author="assistant",
        invocation_id="inv-1",
        actions=SimpleNamespace(),
    )


def build_agent(payload: dict) -> object:
    """Build a mock runner that yields predefined Events per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")

    if mode == "no_tool":
        events = [
            _event(is_final=True, content=_content("I don't have enough information to answer.")),
        ]
    elif mode == "structured":
        structured = {"temperature": 15, "condition": "sunny"}
        events = [
            _event(calls=[_function_call("get_weather", {"city": "London"})]),
            _event(responses=[_function_response("get_weather", {"temp": 15})]),
            _event(is_final=True, content=_content(json.dumps(structured))),
        ]
    else:
        events = [
            _event(calls=[_function_call("get_weather", {"city": "London"})]),
            _event(responses=[_function_response("get_weather", {"temp": 15})]),
            _event(is_final=True, content=_content("The weather in London is 15\u00b0C.")),
        ]

    def run(*, user_id: str, session_id: str, new_message: object):
        yield from events

    return SimpleNamespace(run=run, name="adk_mock_agent")
