"""Mock Claude Agent SDK client for adapter tests.

Exports ``build_agent(payload)`` which returns a mock ``ClaudeSDKClient`` whose
async ``.query(prompt)`` + ``.receive_response()`` mimic ``claude_agent_sdk``
output. Modes are driven by payload context["mode"]:

- ``tool_call``: a tool-use block + tool-result block + final text + result
- ``no_tool``: final text + result only
- ``structured``: final result carries a structured_output dict
"""

from types import SimpleNamespace


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def _tool_use_block(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(id="call_1", name=name, input=args)


def _tool_result_block(content: str) -> SimpleNamespace:
    return SimpleNamespace(tool_use_id="call_1", content=content, is_error=False)


def _assistant_message(blocks: list) -> SimpleNamespace:
    return SimpleNamespace(
        content=blocks,
        model="claude",
        parent_tool_use_id=None,
        error=None,
        usage=None,
        message_id="m-1",
        stop_reason="end_turn",
        session_id="default",
        uuid="u-1",
    )


def _user_message(blocks: list) -> SimpleNamespace:
    return SimpleNamespace(
        content=blocks,
        uuid="u-2",
        parent_tool_use_id=None,
        tool_use_result=None,
    )


def _result_message(
    result: str | None,
    structured_output: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        subtype="result",
        duration_ms=100,
        duration_api_ms=80,
        is_error=False,
        num_turns=1,
        session_id="default",
        stop_reason="end_turn",
        total_cost_usd=0.0,
        usage=None,
        result=result,
        structured_output=structured_output,
        model_usage={"claude": {"inputTokens": 10, "outputTokens": 5, "costUSD": 0.0}},
        permission_denials=None,
        deferred_tool_use=None,
        errors=None,
        api_error_status=None,
        uuid="u-3",
        terminal_reason=None,
    )


def build_agent(payload: dict) -> object:
    """Build a mock ClaudeSDKClient that returns predefined messages per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")

    if mode == "no_tool":
        final = "I don't have enough information to answer."
        messages = [
            _assistant_message([_text_block(final)]),
            _result_message(result=final),
        ]
    elif mode == "structured":
        structured = {"temperature": 15, "condition": "sunny"}
        messages = [
            _assistant_message([_tool_use_block("get_weather", {"city": "London"})]),
            _user_message([_tool_result_block('{"temp": 15}')]),
            _assistant_message([_text_block(str(structured))]),
            _result_message(result=str(structured), structured_output=structured),
        ]
    else:
        final = "The weather in London is 15\u00b0C."
        messages = [
            _assistant_message([_tool_use_block("get_weather", {"city": "London"})]),
            _user_message([_tool_result_block('{"temp": 15}')]),
            _assistant_message([_text_block(final)]),
            _result_message(result=final),
        ]

    async def query(prompt: str, session_id: str = "default") -> None:
        return None

    async def receive_response():
        for message in messages:
            yield message

    return SimpleNamespace(
        query=query,
        receive_response=receive_response,
        name="claude_mock_agent",
    )
