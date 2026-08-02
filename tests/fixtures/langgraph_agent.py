"""Mock LangGraph agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock agent whose
``.invoke(state)`` produces a message list mimicking ``create_react_agent``
output. Modes are driven by payload context context["mode"]:

- ``tool_call``: one tool call + result + final response
- ``multi_tool``: two tool calls + results + final response
- ``no_tool``: final response only (no tool calls)
- ``empty_trajectory``: single response with no tools
"""

from types import SimpleNamespace


def _msg(
    type_: str,
    content: str,
    tool_calls: list | None = None,
    name: str | None = None,
    tool_call_id: str | None = None,
) -> SimpleNamespace:
    ns = SimpleNamespace(type=type_, content=content)
    if tool_calls:
        ns.tool_calls = tool_calls
    if name:
        ns.name = name
    if tool_call_id:
        ns.tool_call_id = tool_call_id
    return ns


def _tool_call(name: str, args: dict, tool_call_id: str) -> SimpleNamespace:
    return _msg("ai", "", tool_calls=[{"name": name, "args": args, "id": tool_call_id}])


def build_agent(payload: dict) -> object:
    """Build a mock agent that returns predefined message sequences."""
    mode = payload.get("context", {}).get("mode", "tool_call")
    values: dict[str, list] = {
        "tool_call": [
            _tool_call("get_weather", {"city": "London"}, "call_1"),
            _msg("tool", '{"temp": 15}', name="get_weather", tool_call_id="call_1"),
            _msg("ai", "The weather in London is 15\u00b0C."),
        ],
        "multi_tool": [
            _tool_call("search", {"q": "weather"}, "call_1"),
            _msg("tool", "sunny", name="search", tool_call_id="call_1"),
            _tool_call("get_forecast", {"day": "tomorrow"}, "call_2"),
            _msg("tool", '{"high": 20}', name="get_forecast", tool_call_id="call_2"),
            _msg("ai", "Tomorrow will be sunny with a high of 20\u00b0C."),
        ],
        "no_tool": [
            _msg("ai", "I don't have enough information to answer."),
        ],
        "empty_trajectory": [],
    }
    msgs = values.get(mode, values["tool_call"])
    return SimpleNamespace(
        invoke=lambda state, config=None: {"messages": msgs},
        name="langgraph_mock_agent",
    )
