"""Quickstart agent — minimal example with no framework dependencies.

Demonstrates the EvalForge PythonImportAdapter contract: a function
``run(payload)`` that returns a run envelope dict.

Usage:
    python examples/quickstart_agent.py

Via EvalForge:
    {"type": "python", "module": "examples.quickstart_agent", "function": "run"}
"""

from __future__ import annotations

import json
from typing import Any


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Echo input and simulate one tool call. No framework dependencies."""
    user = payload.get("input", "")
    tools = payload.get("allowed_tools", [])
    tool_name = tools[0]["name"] if tools else "echo"

    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": f"Echo: {user}", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": tool_name, "args": {"input": user}},
                {"type": "tool_result", "tool": tool_name, "result": f"processed: {user}"},
                {"type": "response", "content": f"Echo: {user}"},
            ]
        },
        "cost": {
            "input_tokens": len(user.split()),
            "output_tokens": 5,
            "total_tokens": len(user.split()) + 5,
            "cost_usd": 0.0,
        },
        "error": None,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Quickstart agent — no framework deps")
    parser.add_argument("--input", default="Hello from quickstart!", help="User input")
    parser.add_argument("--tool", default="echo", help="Tool name to simulate")
    args = parser.parse_args()
    result = run({"input": args.input, "allowed_tools": [{"name": args.tool}]})
    print(json.dumps(result, indent=2))
