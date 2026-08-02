"""LangGraph example agent — hardened for end-to-end EvalForge testing.

Environment variables:
    OPENAI_API_KEY       Required. Your OpenAI/OpenRouter API key.
    OPENAI_BASE_URL      Optional. API endpoint (default: https://api.openai.com/v1).

Usage (standalone):
    python examples/langgraph_agent.py --input "What is 15 * 12?"
    python examples/langgraph_agent.py --model "openai/gpt-4o-mini" --input "Weather in London?"

Usage (via EvalForge adapter):
    {"type": "langgraph", "module": "examples.langgraph_agent", "model": "openai/gpt-4o-mini"}

Tools available in standalone mode:
    calculator  — evaluate arithmetic expressions
    get_weather — get weather for a city (mock)
    search      — search a knowledge base (mock)
"""

from __future__ import annotations

import argparse
import ast
import operator as op
import os
import sys
from typing import Any

# Supported arithmetic operators for the calculator
_SAFE_OPS: dict[type[ast.AST], Any] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
}


def _safe_eval(expr: str) -> float:
    """Safely evaluate a simple arithmetic expression."""
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


def _calculator(expression: str) -> dict[str, Any]:
    """Evaluate a mathematical expression and return the result."""
    try:
        result = _safe_eval(expression)
        return {"expression": expression, "result": result}
    except Exception as exc:
        return {"expression": expression, "error": str(exc)}


def _get_weather(city: str) -> dict[str, Any]:
    """Get the current weather for a city (mock)."""
    return {
        "city": city,
        "temperature": 18,
        "condition": "partly cloudy",
        "humidity": 65,
        "wind_speed_kmh": 12,
    }


def _search(query: str) -> dict[str, Any]:
    """Search a knowledge base (mock)."""
    return {
        "query": query,
        "results": [
            {"title": "Result 1", "snippet": f"Relevant information about {query}."},
            {"title": "Result 2", "snippet": f"More details on {query}."},
        ],
        "total": 2,
    }


STANDALONE_TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports +, -, *, / and parentheses.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate, e.g. '15 * 12'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'London'"}
            },
            "required": ["city"],
        },
    },
    {
        "name": "search",
        "description": "Search a knowledge base for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"}
            },
            "required": ["query"],
        },
    },
]

_TOOL_IMPLS: dict[str, Any] = {
    "calculator": _calculator,
    "get_weather": _get_weather,
    "search": _search,
}


def _resolve_tool_implementations(tool_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach callable implementations to tool specs where we have them."""
    resolved: list[dict[str, Any]] = []
    for spec in tool_specs:
        name = spec.get("name", "")
        impl = _TOOL_IMPLS.get(name)
        entry = dict(spec)
        if impl is not None:
            entry["func"] = impl
        resolved.append(entry)
    return resolved


def resolve_target_model(model: str | None = None) -> str:
    """Resolve the target model string.

    If no model is given, fall back to the environment variable EVALFORGE_FIELD_MODEL
    (set by the field test runner) or a sensible default.

    Returns the model string to pass to create_react_agent.
    """
    if model:
        return model
    env_model = os.environ.get("EVALFORGE_FIELD_MODEL")
    if env_model:
        return env_model
    return "openai:gpt-4o-mini"


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
    """Build a ReAct agent for the given scenario payload.

    This is the EvalForge adapter entry point. The adapter calls this function
    and then invokes the returned agent with the scenario input.

    Args:
        payload: Scenario payload with 'input', 'allowed_tools', 'disallowed_tools'.
        model: Optional model name override.
    """
    from langgraph.prebuilt import create_react_agent

    ensure_openai_api_key()
    model_name = resolve_target_model(model)
    tools_raw = payload.get("allowed_tools") or STANDALONE_TOOLS
    tools = _resolve_tool_implementations(tools_raw)
    return create_react_agent(model_name, tools=tools)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LangGraph example agent — run a prompt through a ReAct agent"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (default: openai:gpt-4o-mini or EVALFORGE_FIELD_MODEL env)",
    )
    parser.add_argument(
        "--input",
        default="What is 15 * 12?",
        help="User input prompt (default: 'What is 15 * 12?')",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    payload = {
        "input": args.input,
        "allowed_tools": STANDALONE_TOOLS,
        "disallowed_tools": [],
    }
    agent = build_agent(payload, model=args.model)
    result = agent.invoke({"messages": [{"role": "user", "content": args.input}]})
    for msg in result["messages"]:
        tc = getattr(msg, "tool_calls", None)
        if tc:
            for t in tc:
                print(f"[tool_call] {t.get('name', '?')}: {t.get('args', {})}")
        elif getattr(msg, "type", None) == "tool":
            print(f"[tool_result] {getattr(msg, 'name', '?')}: {getattr(msg, 'content', '')}")
        else:
            content = getattr(msg, "content", "")
            if content:
                print(f"[assistant] {content}")
