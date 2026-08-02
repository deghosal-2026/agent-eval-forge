"""Adapter factory: resolve an adapter from an agent config dict.

``agent_config["type"]`` selects which adapter to build. The factory is the
single lookup point so the Runner (and, later, the CLI) can turn a YAML agent
block into a ready adapter without import gymnastics. Adding a new adapter
type means registering it in ``ADAPTERS``.

Exports:
    ADAPTERS: Mapping of type strings to adapter classes.
    create_adapter: Factory function to instantiate an adapter from config.
"""

from __future__ import annotations

from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.adapters.http import HttpAdapter
from evalforge.adapters.isolated import IsolatedAdapter
from evalforge.adapters.langgraph import LangGraphAdapter
from evalforge.adapters.pydantic_ai import PydanticAIAdapter
from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.adapters.subprocess import SubprocessAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "subprocess": SubprocessAdapter,
    "python": PythonImportAdapter,
    "http": HttpAdapter,
    "langgraph": LangGraphAdapter,
    "pydantic-ai": PydanticAIAdapter,
    "isolated": IsolatedAdapter,
}


def create_adapter(config: dict[str, Any]) -> Adapter:
    """Return an adapter instance for the given agent config.

    Args:
        config: Agent configuration dict; must contain a ``type`` key
            matching one of the keys in :data:`ADAPTERS`.

    Returns:
        An initialized adapter instance.

    Raises:
        ValueError: If ``config["type"]`` is not a registered adapter type.
    """
    adapter_type = config.get("type")
    try:
        adapter_cls = ADAPTERS[adapter_type]
    except KeyError as exc:
        raise ValueError(f"unknown adapter type: {adapter_type}") from exc
    return adapter_cls()
