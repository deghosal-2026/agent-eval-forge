"""PydanticAI example agent — hardened for end-to-end EvalForge testing.

Environment variables:
    OPENAI_API_KEY       Required. Your OpenAI/OpenRouter API key.
    OPENAI_BASE_URL      Optional. API endpoint (default: https://api.openai.com/v1).

Usage (standalone):
    python examples/pydantic_ai_agent.py --input "Weather in London?"
    python examples/pydantic_ai_agent.py --model "openai/gpt-4o-mini" --input "What is 15 * 12?"

Usage (via EvalForge adapter):
    {"type": "pydantic-ai", "module": "examples.pydantic_ai_agent", "model": "openai/gpt-4o-mini"}

Tools available in standalone mode:
    get_weather — get weather for a city (mock)
    calculator  — evaluate arithmetic expressions

Structured output in standalone mode: WeatherResult (temperature, condition, city).
"""

from __future__ import annotations

import argparse
import ast
import operator as op
import os
import sys
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

# ── Structured output model ────────────────────────────────────────────────


@dataclass
class WeatherResult:
    temperature: float
    condition: str
    city: str


# ── Tool implementations ───────────────────────────────────────────────────

_SAFE_OPS: dict[type[ast.AST], Any] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
}


def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    return float(_eval_node(tree.body))


def _eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


def _get_weather(city: str) -> dict[str, Any]:
    """Get the current weather for a city (mock)."""
    return {"temperature": 18, "condition": "partly cloudy", "city": city}


def _calculator(expression: str) -> dict[str, Any]:
    """Evaluate a mathematical expression and return the result."""
    try:
        result = _safe_eval(expression)
        return {"expression": expression, "result": result}
    except Exception as exc:
        return {"expression": expression, "error": str(exc)}


# ── Module-level agent (standalone default, lazy-init) ────────────────────

_weather_agent: Any = None


def _get_default_agent() -> Any:
    """Return the module-level weather agent, creating it on first access."""
    global _weather_agent
    if _weather_agent is None:
        ensure_openai_api_key()
        agent = Agent(
            "openai:gpt-4o-mini",
            output_type=WeatherResult,
            system_prompt="You are a helpful assistant with weather and calculation tools.",
        )

        @agent.tool_plain
        def _standalone_get_weather(city: str) -> dict[str, Any]:
            return _get_weather(city)

        @agent.tool_plain
        def _standalone_calculator(expression: str) -> dict[str, Any]:
            return _calculator(expression)

        _weather_agent = agent
    return _weather_agent


# ── Entry point ─────────────────────────────────────────────────────────────


def ensure_openai_api_key() -> str:
    """Return the OpenAI API key, or exit with a clear message if missing."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print(
            "Error: OPENAI_API_KEY environment variable is required.\n"
            "Set it before running this agent, e.g.:\n"
            "  export OPENAI_API_KEY=sk-or-v1-...",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def build_agent(payload: dict[str, Any], model: str | None = None) -> Any:
    """Build a PydanticAI agent for the given scenario payload.

    This is the EvalForge adapter entry point. The adapter calls this function
    and then invokes the returned agent with the scenario input via .run_sync().

    If the payload provides allowed_tools, a fresh Agent is created with those
    tools. Otherwise, the module-level weather_agent is returned as default.

    Args:
        payload: Scenario payload with 'input', 'allowed_tools', 'disallowed_tools'.
        model: Optional model name override (e.g. 'openai/gpt-4o').
    """
    ensure_openai_api_key()
    model_name = model or "openai:gpt-4o-mini"

    tools_raw = payload.get("allowed_tools")
    if not tools_raw:
        return _get_default_agent()

    # Build a dynamic agent with scenario-provided tools
    agent = Agent(
        model_name,
        system_prompt="You are a helpful assistant. Use the provided tools when needed.",
    )

    for tool_spec in tools_raw:
        name = tool_spec.get("name", "")
        if name == "calculator":

            @agent.tool_plain
            def _calc(expression: str) -> dict[str, Any]:
                return _calculator(expression)

        elif name == "get_weather":

            @agent.tool_plain
            def _w(city: str) -> dict[str, Any]:
                return _get_weather(city)

        elif name == "search":

            @agent.tool_plain
            def _s(query: str) -> dict[str, Any]:
                return {
                    "query": query,
                    "results": [{"title": "Result 1", "snippet": f"Info about {query}."}],
                    "total": 1,
                }

        # Other tool names are passed through — the LLM will attempt to call them
        # but they will fail at runtime unless the agent provides an implementation.
        # This is by design: scenarios that need custom tools should provide
        # implementations or use fixture-backed agents.

    return agent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PydanticAI example agent — run a prompt with structured output"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (default: openai:gpt-4o-mini)",
    )
    parser.add_argument(
        "--input",
        default="What is the weather in London?",
        help="User input prompt (default: 'What is the weather in London?')",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    import asyncio

    args = parse_args()
    payload = {
        "input": args.input,
        "allowed_tools": None,
        "disallowed_tools": [],
    }
    agent = build_agent(payload, model=args.model)
    result = asyncio.run(agent.run(args.input))
    if result.data:
        print(f"[structured] {result.data}")
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            kind = part.kind() if hasattr(part, "kind") else ""
            if kind == "tool-call":
                print(
                    f"[tool_call] {getattr(part, 'tool_name', '?')}: "
                    f"{getattr(part, 'args', {})}"
                )
            elif kind == "tool-return":
                print(
                    f"[tool_result] {getattr(part, 'tool_name', '?')}: "
                    f"{getattr(part, 'content', '')}"
                )
            elif kind == "final":
                print(f"[assistant] {getattr(part, 'content', '')}")
