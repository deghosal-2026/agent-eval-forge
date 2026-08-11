"""Mock CrewAI agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock Crew whose
``.kickoff(inputs)`` returns a CrewOutput mimicking ``crewai.CrewOutput``.
Modes driven by payload context["mode"]:

- ``tool_call``: one tool-using task + final response (with messages)
- ``no_tool``: final response only
- ``structured``: structured (json_dict) output
"""

from types import SimpleNamespace


def _task(
    raw: str,
    messages: list[dict] | None = None,
    tool_name: str | None = None,
    tool_arguments: dict | None = None,
) -> SimpleNamespace:
    ns = SimpleNamespace(raw=raw, messages=messages or [])
    if tool_name:
        ns.tool_name = tool_name
    if tool_arguments:
        ns.tool_arguments = tool_arguments
    return ns


def _usage() -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def build_agent(payload: dict) -> object:
    """Build a mock Crew that returns predefined CrewOutput per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")

    if mode == "no_tool":
        tasks = [_task("I don't have enough information to answer.")]
        raw = "I don't have enough information to answer."
        json_dict = None
    elif mode == "structured":
        tasks = [_task('{"temperature": 15, "condition": "sunny"}')]
        raw = '{"temperature": 15, "condition": "sunny"}'
        json_dict = {"temperature": 15, "condition": "sunny"}
    else:
        tasks = [
            _task(
                '{"temp": 15}',
                messages=[
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "London"}',
                                }
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "name": "get_weather",
                        "content": '{"temp": 15}',
                    },
                ],
                tool_name="get_weather",
                tool_arguments={"city": "London"},
            ),
            _task("The weather in London is 15\u00b0C."),
        ]
        raw = "The weather in London is 15\u00b0C."
        json_dict = None

    output = SimpleNamespace(raw=raw, tasks_output=tasks, token_usage=_usage(), json_dict=json_dict)
    return SimpleNamespace(
        kickoff=lambda inputs=None: output,
        name="crewai_mock_crew",
    )
