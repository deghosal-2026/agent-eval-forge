from __future__ import annotations

import importlib
from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError


class LangGraphAdapter(Adapter):
    name = "langgraph"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        module_name = config.get("module")
        if not module_name:
            raise AdapterError("langgraph adapter requires `module` in config")

        function_name = config.get("function", "build_agent")
        model_override = config.get("model")

        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            raise AdapterError(
                f"cannot import module '{module_name}': {exc}. "
                "If this is a langgraph agent, install with: pip install evalforge[langgraph]"
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

        if not hasattr(agent, "invoke"):
            raise AdapterError(
                "build_agent must return an object with an .invoke() method"
            )

        user_input = payload.get("input", "")
        initial_state = {"messages": [{"role": "user", "content": user_input}]}

        try:
            result = agent.invoke(initial_state)
        except Exception as exc:
            raise AdapterError(f"agent invocation failed: {exc}") from exc

        if not isinstance(result, dict) or "messages" not in result:
            raise AdapterError("agent result missing 'messages' key")

        messages = result["messages"]
        steps, final_content = _extract_trajectory(messages)

        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": final_content, "structured": None},
            "trajectory": {"steps": steps},
            "cost": None,
            "error": None,
        }


def _extract_trajectory(
    messages: list[Any],
) -> tuple[list[dict[str, Any]], str | None]:
    steps: list[dict[str, Any]] = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({
                    "type": "tool_call",
                    "tool": tc["name"],
                    "args": tc.get("args", {}),
                    "duration_ms": None,
                })
        elif getattr(msg, "type", None) == "tool":
            steps.append({
                "type": "tool_result",
                "tool": getattr(msg, "name", msg.tool_call_id) or "",
                "result": getattr(msg, "content", ""),
                "duration_ms": None,
            })

    final_content: str | None = None
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" and not getattr(msg, "tool_calls", None):
            final_content = getattr(msg, "content", None) or ""
            break

    if final_content is not None:
        steps.append({
            "type": "response",
            "content": final_content,
            "duration_ms": None,
        })

    return steps, final_content
