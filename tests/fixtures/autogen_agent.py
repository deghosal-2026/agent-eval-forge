"""Mock AutoGen agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock ``AssistantAgent`` whose
async ``.run(*, task=...)`` returns a ``TaskResult`` mimicking
``autogen_agentchat`` output. Modes are driven by payload context["mode"]:

- ``tool_call``: a tool-call summary message + final text response
- ``no_tool``: final text response only
- ``structured``: final text response is a JSON dict (structured)
"""

from types import SimpleNamespace


def _function_call(name: str, args: dict) -> SimpleNamespace:
    import json
    return SimpleNamespace(id="call_1", arguments=json.dumps(args), name=name)


def _function_result(content: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(content=content, name=name, call_id="call_1", is_error=False)


def _text_message(content: str, usage: SimpleNamespace | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="m-1",
        source="assistant",
        models_usage=usage,
        metadata={},
        created_at="2026-01-01T00:00:00Z",
        content=content,
        type="TextMessage",
    )


def _tool_summary_message(
    calls: list, results: list, usage: SimpleNamespace | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        id="m-2",
        source="assistant",
        models_usage=usage,
        metadata={},
        created_at="2026-01-01T00:00:00Z",
        content="",
        type="ToolCallSummaryMessage",
        tool_calls=calls,
        results=results,
    )


def _usage(prompt: int = 10, completion: int = 5) -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def build_agent(payload: dict) -> object:
    """Build a mock AssistantAgent that returns a predefined TaskResult per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")
    usage = _usage(10, 5)

    if mode == "no_tool":
        messages = [_text_message("I don't have enough information to answer.", usage)]
    elif mode == "structured":
        import json
        messages = [
            _text_message("I'll check the weather."),
            _tool_summary_message(
                calls=[_function_call("get_weather", {"city": "London"})],
                results=[_function_result('{"temp": 15}', "get_weather")],
                usage=usage,
            ),
            _text_message(json.dumps({"temperature": 15, "condition": "sunny"})),
        ]
    else:
        messages = [
            _text_message("I'll check the weather."),
            _tool_summary_message(
                calls=[_function_call("get_weather", {"city": "London"})],
                results=[_function_result('{"temp": 15}', "get_weather")],
                usage=usage,
            ),
            _text_message("The weather in London is 15\u00b0C."),
        ]

    result = SimpleNamespace(messages=messages, stop_reason="done")

    async def run(*, task: str | None = None, **kwargs: object) -> object:
        return result

    return SimpleNamespace(run=run, name="autogen_mock_agent")
