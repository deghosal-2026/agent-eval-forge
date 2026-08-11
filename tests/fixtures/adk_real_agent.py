"""Real ADK agent backed by local OMLX LLM for LLM-backed adapter tests.

Produces duck-typed ``Event`` objects via a ``run`` generator that the
``ADKAdapter`` can walk, using the OpenAI client directly to call the OMLX
server.
"""

import json
import os
from types import SimpleNamespace
from typing import Any

from openai import OpenAI


def _make_event(
    *,
    func_calls: list | None = None,
    func_responses: list | None = None,
    final_text: str | None = None,
) -> SimpleNamespace:
    has_final = final_text is not None
    content = None
    if final_text:
        content = SimpleNamespace(parts=[SimpleNamespace(text=final_text)])
    return SimpleNamespace(
        get_function_calls=lambda: func_calls or [],
        get_function_responses=lambda: func_responses or [],
        is_final_response=lambda: has_final,
        content=content,
        author="assistant",
        invocation_id="inv-1",
        actions=SimpleNamespace(),
    )


def _fc(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(id="call_1", name=name, args=args)


def _fr(name: str, response: dict) -> SimpleNamespace:
    return SimpleNamespace(id="call_1", name=name, response=response)


def build_agent(payload: dict | None = None) -> object:
    """Build a duck-typed runner whose ``.run(**kw)`` yields ADK-like events."""
    mode = (payload or {}).get("context", {}).get("mode", "tool_call")

    def run(*, user_id: str, session_id: str, new_message: object) -> Any:
        base_url = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")
        api_key = os.environ.get("OPENAI_API_KEY", "omlx-test")
        model = os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit")
        client = OpenAI(base_url=base_url, api_key=api_key)

        if mode == "no_tool":
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": str(new_message)}],
            )
            yield _make_event(final_text=resp.choices[0].message.content or "")
            return

        # tool-call flow
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "City name."}},
                    "required": ["city"],
                },
            },
        }]
        msgs = [{"role": "user", "content": str(new_message)}]
        resp1 = client.chat.completions.create(
            model=model, messages=msgs, tools=tools, tool_choice="auto"
        )
        choice1 = resp1.choices[0]

        if choice1.message.tool_calls:
            tool_call = choice1.message.tool_calls[0]
            fn = tool_call.function
            try:
                args = json.loads(fn.arguments) if fn.arguments else {}
            except (ValueError, TypeError):
                args = {}
            yield _make_event(func_calls=[_fc(fn.name, args)])

            city = args.get("city", "")
            sunny = "The weather in London is 15C and sunny."
            unavailable = f"Weather data not available for {city}."
            result = sunny if "london" in city.lower() else unavailable
            yield _make_event(func_responses=[_fr(fn.name, {"temp": 15})])

            msgs.append({"role": "assistant", "tool_calls": [tool_call.model_dump()]})
            msgs.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
            resp2 = client.chat.completions.create(model=model, messages=msgs)
            yield _make_event(final_text=resp2.choices[0].message.content or "")
        else:
            yield _make_event(final_text=choice1.message.content or "")

    return SimpleNamespace(run=run, name="adk_real_agent")
