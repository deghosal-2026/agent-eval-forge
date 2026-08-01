from __future__ import annotations

import importlib
from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError


class PydanticAIAdapter(Adapter):
    name = "pydantic-ai"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        module_name = config.get("module")
        if not module_name:
            raise AdapterError("pydantic-ai adapter requires `module` in config")

        function_name = config.get("function", "build_agent")
        model_override = config.get("model")

        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            raise AdapterError(
                f"cannot import module '{module_name}': {exc}. "
                "If this is a pydantic-ai agent, install with: pip install evalforge[pydanticai]"
            ) from exc

        try:
            builder = getattr(mod, function_name)
        except AttributeError as exc:
            raise AdapterError(
                f"module '{module_name}' has no function '{function_name}'"
            ) from exc

        try:
            kwargs: dict[str, Any] = {}
            if model_override:
                kwargs["model"] = model_override
            agent = builder(payload, **kwargs)
        except Exception as exc:
            raise AdapterError(f"build_agent failed: {exc}") from exc

        if not hasattr(agent, "run_sync"):
            raise AdapterError(
                "build_agent must return an object with a .run_sync() method"
            )

        user_input = payload.get("input", "")

        try:
            result = agent.run_sync(user_input)
        except Exception as exc:
            raise AdapterError(f"agent invocation failed: {exc}") from exc

        all_messages = result.all_messages() if hasattr(result, "all_messages") else []
        steps, final_content = _extract_trajectory(all_messages)

        structured = getattr(result, "data", None)
        if structured is not None and not isinstance(structured, str):
            final_content = final_content or str(structured)

        structured_output = structured if isinstance(structured, dict) else None
        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": final_content, "structured": structured_output},
            "trajectory": {"steps": steps},
            "cost": _extract_cost(result),
            "error": None,
        }


def _extract_trajectory(
    all_messages: list[Any],
) -> tuple[list[dict[str, Any]], str | None]:
    steps: list[dict[str, Any]] = []
    final_content: str | None = None

    for msg in all_messages:
        parts = getattr(msg, "parts", [])
        if not parts:
            continue
        for part in parts:
            kind = part.kind() if hasattr(part, "kind") else ""
            if kind == "tool-call":
                steps.append({
                    "type": "tool_call",
                    "tool": getattr(part, "tool_name", ""),
                    "args": getattr(part, "args", {}),
                    "duration_ms": None,
                })
            elif kind == "tool-return":
                steps.append({
                    "type": "tool_result",
                    "tool": getattr(part, "tool_name", ""),
                    "result": getattr(part, "content", None),
                    "duration_ms": None,
                })
            elif kind == "final":
                final_content = getattr(part, "content", "") or ""

    if final_content:
        steps.append({
            "type": "response",
            "content": final_content,
            "duration_ms": None,
        })

    return steps, final_content


def _extract_cost(result: Any) -> dict[str, Any] | None:
    """Extract usage/cost if the result has a .usage() method (pydantic-ai >=0.0.10)."""
    if not hasattr(result, "usage"):
        return None
    try:
        usage = result.usage()
    except Exception:
        return None
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "request_tokens", 0),
        "output_tokens": getattr(usage, "response_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
        "cost_usd": 0.0,
    }
