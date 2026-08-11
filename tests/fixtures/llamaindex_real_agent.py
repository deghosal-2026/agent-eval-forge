"""Real LlamaIndex agent backed by local OMLX LLM for LLM-backed adapter tests.

Wraps the OpenAI client to produce AgentChatResponse-like results that the
LlamaIndexAdapter can parse, avoiding FunctionAgent's model-name validation.
"""

import json
import os
from types import SimpleNamespace
from typing import Any

from openai import OpenAI


def _chat_completion(client: OpenAI, user_msg: str, tools: list | None = None) -> Any:
    kwargs: dict = {
        "model": os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit"),
        "messages": [{"role": "user", "content": user_msg}],
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message

    sources: list = []
    final_response: str = msg.content or ""

    if msg.tool_calls:
        for tc in msg.tool_calls:
            fn = tc.function
            tool_args = json.loads(fn.arguments) if fn.arguments else {}
            tool_name = fn.name

            result_content = ""
            if tool_name == "get_weather" and "london" in str(tool_args.get("city", "")).lower():
                result_content = "The weather in London is 15C and sunny."
            else:
                result_content = f"Weather data not available for {tool_args.get('city', '?')}."

            sources.append(SimpleNamespace(
                tool_name=tool_name,
                raw_input=tool_args,
                raw_output=result_content,
                is_error=False,
                blocks=[],
            ))

            kwargs["messages"].append({
                "role": "assistant",
                "tool_calls": [tc.model_dump()],
            })
            kwargs["messages"].append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_content,
            })

        kwargs.pop("tool_choice", None)
        final_resp = client.chat.completions.create(**kwargs)
        final_response = final_resp.choices[0].message.content or ""
        del kwargs["tools"]

    return SimpleNamespace(
        response=final_response,
        sources=sources,
        source_nodes=[],
        is_dummy_stream=False,
        metadata={},
    )


def build_agent(payload: dict | None = None) -> object:
    """Build a duck-typed agent with async chat(user_msg=...) using OMLX."""
    mode = (payload or {}).get("context", {}).get("mode", "tool_call")
    base_url = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "omlx-test")
    client = OpenAI(base_url=base_url, api_key=api_key)

    tools = None
    if mode != "no_tool":
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "The city name."},
                    },
                    "required": ["city"],
                },
            },
        }]

    async def chat(user_msg: str | None = None, **kwargs: object) -> object:
        return _chat_completion(client, user_msg or "", tools)

    return SimpleNamespace(chat=chat, name="llamaindex_real_agent")
