"""Shared utilities for CLI commands.

This module provides helpers shared across CLI commands to avoid
duplication. Currently includes agent spec parsing; add shared functions
here rather than copying between command modules.
"""

from __future__ import annotations

from typing import Any


def parse_agent_spec(agent_spec: str) -> dict[str, Any]:
    """Parse an agent spec string into a configuration dictionary.

    The spec string follows the format ``<adapter_type>:<value>`` where
    adapters determine how ``value`` is interpreted:

    ============== =================== =========================================
    Adapter type   Value               Example
    ============== =================== =========================================
    ``python``     Dotted module path  ``python:my_agent.run``
    ``langgraph``  Dotted module path  ``langgraph:examples.my_agent.build``
    ``pydantic-ai`` Dotted module path ``pydantic-ai:examples.my_agent.build``
    ``http``       URL                 ``http:http://localhost:8000/agent``
    ``subprocess`` Command/path        ``subprocess:./my_agent.sh``
    (none given)   Command/path        ``./my_agent.sh`` (defaults to subprocess)
    ============== =================== =========================================

    Args:
        agent_spec: The agent spec string to parse.

    Returns:
        A configuration dictionary with at least a ``type`` key. Additional
        keys (``module``, ``command``, ``url``) are added based on the type.

    Raises:
        click.BadParameter: If the adapter type is not recognized.
    """
    # Split on first colon to separate adapter type from the value
    parts = agent_spec.split(":", 1)
    if len(parts) == 1:
        # Bare command — default to subprocess adapter
        return {"type": "subprocess", "command": agent_spec}

    adapter_type = parts[0]
    value = parts[1]
    cfg: dict[str, Any] = {"type": adapter_type}

    if adapter_type in ("python", "langgraph", "pydantic-ai"):
        # Framework adapters use Python module resolution.
        # Support "module" and "module:function" forms:
        #   python:my_module        → module="my_module", function="run" (default)
        #   python:my_module:run    → module="my_module", function="run"
        #   python:pkg.mod:myfunc   → module="pkg.mod", function="myfunc"
        module_value = value.rsplit(":", 1)
        if len(module_value) == 2:
            cfg["module"] = module_value[0]
            cfg["function"] = module_value[1]
        else:
            cfg["module"] = value
    elif adapter_type == "http":
        cfg["url"] = value
    elif adapter_type == "subprocess":
        cfg["command"] = value
    else:
        # Defer the import so we only pay it on error paths
        from click import BadParameter

        raise BadParameter(f"unknown adapter type: {adapter_type}")

    return cfg
