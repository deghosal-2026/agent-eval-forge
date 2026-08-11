"""Mock smolagents agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock CodeAgent whose
``.run(task, return_full_result=True)`` returns a RunResult mimicking
``smolagents.agents.RunResult``. Modes are driven by payload
context["mode"]:

- ``tool_call``: one tool call + observation + final answer
- ``no_tool``: final answer only
- ``structured``: final output is a dict (structured)
"""

from types import SimpleNamespace


def _tool_call(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(name=name, arguments=args, id="call_1")


def _step(
    calls: list | None = None,
    observations: list | None = None,
    token_usage: SimpleNamespace | None = None,
    is_final: bool = False,
    action_output: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tool_calls=calls or [],
        observations=observations or [],
        token_usage=token_usage,
        is_final_answer=is_final,
        action_output=action_output,
        error=None,
    )


def _usage() -> SimpleNamespace:
    return SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)


def build_agent(payload: dict) -> object:
    """Build a mock CodeAgent that returns predefined RunResults per mode."""
    mode = payload.get("context", {}).get("mode", "tool_call")

    if mode == "no_tool":
        output = "I don't have enough information to answer."
        steps = [_step(is_final=True, action_output=output, token_usage=_usage())]
    elif mode == "structured":
        output = {"temperature": 15, "condition": "sunny"}
        steps = [
            _step(
                calls=[_tool_call("get_weather", {"city": "London"})],
                observations=['{"temp": 15}'],
                token_usage=_usage(),
            ),
            _step(is_final=True, action_output=str(output)),
        ]
    else:
        output = "The weather in London is 15\u00b0C."
        steps = [
            _step(
                calls=[_tool_call("get_weather", {"city": "London"})],
                observations=['{"temp": 15}'],
                token_usage=_usage(),
            ),
            _step(is_final=True, action_output=output),
        ]

    result = SimpleNamespace(output=output, steps=steps, token_usage=_usage())

    def run(task: str | None = None, return_full_result: bool = False, **kwargs: object) -> object:
        if return_full_result:
            return result
        return result.output

    return SimpleNamespace(
        run=run,
        memory=SimpleNamespace(get_full_steps=lambda: steps),
        steps=steps,
        name="smolagents_mock_agent",
    )

