"""Worker process for IsolatedAdapter. Run via: python -m evalforge.adapters.worker

Reads a JSON payload from stdin containing adapter metadata and the invocation
payload, imports the agent module, invokes the agent, and writes a JSON run
envelope to stdout.

The payload structure expected on stdin:
{
    "adapter_type": "langgraph" | "pydantic-ai",
    "module": "<python module path>",
    "function": "<builder function name>",
    "model": "<optional model override>",
    "payload": { <invocation payload> }
}

Exports:
    main: Entry point that reads stdin, dispatches to the appropriate adapter
        handler, and prints the run envelope.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
import uuid
from typing import Any


def _load_payload() -> dict[str, Any]:
    """Read and parse a JSON object from stdin.

    Returns:
        The parsed JSON payload as a dict.

    Raises:
        RuntimeError: If stdin does not contain a JSON object.
    """
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        raise RuntimeError("stdin payload must be a JSON object")
    return data


def _call_builder(builder: Any, payload: dict[str, Any], model: str | None) -> Any:
    """Call a builder function, passing the payload only if it requires positional args.

    Inspects the builder's signature to determine whether it accepts positional
    arguments. If it has no required positional parameters, calls it with just
    kwargs (e.g., model override). Otherwise, passes the payload as the first
    positional argument.

    Args:
        builder: The builder function or class to call.
        payload: The invocation payload dict.
        model: Optional model name override.

    Returns:
        The return value of the builder (typically an agent instance).
    """
    kwargs: dict[str, Any] = {}
    if model:
        kwargs["model"] = model
    sig = inspect.signature(builder)
    required = [
        p
        for p in sig.parameters.values()
        if p.default is inspect._empty
        and p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if not required:
        return builder(**kwargs)
    return builder(payload, **kwargs)


def _langgraph(
    payload: dict[str, Any], module: str, function: str, model: str | None
) -> dict[str, Any]:
    """Handle a LangGraph agent invocation in the worker process.

    Imports the module, resolves the builder (either a pre-built invokable or
    a factory function), invokes the compiled graph, and extracts trajectory
    steps from the message list.

    Args:
        payload: The invocation payload with ``input`` key.
        module: Python module path.
        function: Builder function name.
        model: Optional model override.

    Returns:
        A run envelope dict with status, output, trajectory, cost, and error.
    """
    mod = importlib.import_module(module)
    builder = getattr(mod, function)
    if hasattr(builder, "invoke"):
        agent = builder
    else:
        agent = _call_builder(builder, payload, model)
    _tid = str(uuid.uuid4())
    result = agent.invoke(
        {
            "messages": [{"role": "user", "content": payload.get("input", "")}],
            "task_id": _tid,
        },
        {"configurable": {"thread_id": _tid, "task_id": _tid}},
    )
    messages = result.get("messages", []) if isinstance(result, dict) else []
    steps: list[dict[str, Any]] = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append(
                    {
                        "type": "tool_call",
                        "tool": (
                            tc.get("name", "")
                            if isinstance(tc, dict)
                            else getattr(tc, "name", "")
                        ),
                        "args": (
                            tc.get("args", {})
                            if isinstance(tc, dict)
                            else getattr(tc, "args", {})
                        ),
                        "duration_ms": None,
                    }
                )
        elif getattr(msg, "type", None) == "tool":
            steps.append(
                {
                    "type": "tool_result",
                    "tool": getattr(msg, "name", msg.tool_call_id) or "",
                    "result": getattr(msg, "content", ""),
                    "duration_ms": None,
                }
            )

    final = None
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" and not getattr(msg, "tool_calls", None):
            final = getattr(msg, "content", None) or ""
            break

    if final:
        steps.append({"type": "response", "content": final, "duration_ms": None})
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": final, "structured": None},
        "trajectory": {"steps": steps},
        "cost": None,
        "error": None,
    }


def _pydantic_ai(
    payload: dict[str, Any], module: str, function: str, model: str | None
) -> dict[str, Any]:
    """Handle a PydanticAI agent invocation in the worker process.

    Imports the module, resolves the builder (either a pre-built agent with
    ``run_sync`` or a factory function), invokes the agent, and extracts
    trajectory steps from message parts. Structured output (result.data) is
    included when it is a dict.

    Args:
        payload: The invocation payload with ``input`` key.
        module: Python module path.
        function: Builder function name.
        model: Optional model override.

    Returns:
        A run envelope dict with status, output, trajectory, cost, and error.
    """
    mod = importlib.import_module(module)
    builder = getattr(mod, function)
    if hasattr(builder, "run_sync"):
        agent = builder
    else:
        agent = _call_builder(builder, payload, model)
    result = agent.run_sync(payload.get("input", ""))
    final = None
    steps: list[dict[str, Any]] = []
    for msg in result.all_messages() if hasattr(result, "all_messages") else []:
        for part in getattr(msg, "parts", []):
            kind = part.kind() if hasattr(part, "kind") else ""
            if kind == "tool-call":
                steps.append(
                    {
                        "type": "tool_call",
                        "tool": getattr(part, "tool_name", ""),
                        "args": getattr(part, "args", {}),
                        "duration_ms": None,
                    }
                )
            elif kind == "tool-return":
                steps.append(
                    {
                        "type": "tool_result",
                        "tool": getattr(part, "tool_name", ""),
                        "result": getattr(part, "content", None),
                        "duration_ms": None,
                    }
                )
            elif kind == "final":
                final = getattr(part, "content", "") or final
    structured = getattr(result, "data", None)
    if structured is not None and not isinstance(structured, str):
        final = final or str(structured)
    if final:
        steps.append({"type": "response", "content": final, "duration_ms": None})
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {
            "final": final,
            "structured": structured if isinstance(structured, dict) else None,
        },
        "trajectory": {"steps": steps},
        "cost": None,
        "error": None,
    }


def _error_envelope(exc: Exception) -> dict[str, Any]:
    """Build a run envelope representing an error state.

    Args:
        exc: The exception that occurred.

    Returns:
        A run envelope with status "error" and the exception's message.
    """
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "error",
        "output": {"final": None, "structured": None},
        "trajectory": {"steps": []},
        "cost": None,
        "error": str(exc),
    }


def main() -> int:
    """Entry point: read payload from stdin, dispatch, and print result.

    Parses the stdin JSON, selects the handler based on ``adapter_type``
    ("langgraph" or "pydantic-ai"), and writes the resulting run envelope
    as JSON to stdout. Any exception during processing is caught and
    rendered as an error envelope.

    Returns:
        0 on success (the envelope is always written to stdout).
    """
    data = _load_payload()
    adapter_type = data.get("adapter_type", "")
    module = data.get("module", "")
    function = data.get("function", "build_agent")
    model = data.get("model")
    invocation_payload = data.get("payload", {})

    try:
        if adapter_type == "langgraph":
            envelope = _langgraph(invocation_payload, module, function, model)
        elif adapter_type == "pydantic-ai":
            envelope = _pydantic_ai(invocation_payload, module, function, model)
        else:
            envelope = _error_envelope(RuntimeError(f"unknown adapter_type: {adapter_type}"))
    except Exception as exc:
        envelope = _error_envelope(exc)

    print(json.dumps(envelope))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
