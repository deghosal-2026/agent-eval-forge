"""Pytest fixtures for LangGraph testing.

Provides ``compiled_graph_with_memory`` — a minimal two-node StateGraph
with an in-memory checkpointer — and ``node_mock_env`` — a context-manager
factory that replaces LLM invocations with canned responses.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest


@pytest.fixture
def compiled_graph_with_memory() -> Any:
    """Return a compiled two-node StateGraph with an in-memory checkpointer.

    Graph layout::

        entry → [echo] → [process] → finish

    - ``echo`` copies ``input`` to ``echoed`` and records its name in ``node_history``.
    - ``process`` prepends ``"processed:"`` to ``input`` and records its name.

    Returns:
        A compiled ``langgraph.graph.CompiledStateGraph`` backed by
        ``MemorySaver``.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph

    builder = StateGraph(dict)  # type: ignore[type-var]

    def echo_node(state: dict[str, Any]) -> dict[str, Any]:
        state["echoed"] = state.get("input", "")
        state["node_history"] = [*state.get("node_history", []), "echo"]
        return state

    def process_node(state: dict[str, Any]) -> dict[str, Any]:
        val = state.get("input", "")
        state["processed"] = f"processed:{val}"
        state["node_history"] = [*state.get("node_history", []), "process"]
        return state

    builder.add_node("echo", echo_node)  # type: ignore[type-var]
    builder.add_node("process", process_node)  # type: ignore[type-var]
    builder.set_entry_point("echo")
    builder.add_edge("echo", "process")
    builder.set_finish_point("process")

    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    return graph


@pytest.fixture
def node_mock_env() -> Any:
    """Return a factory that wraps LLM calls in a mock context manager.

    Usage inside a test::

        env = node_mock_env()
        with env(responses=["Hello", "World"]) as mock_llm:
            result = mock_llm.invoke("...")

    Returns:
        A callable that takes an optional ``responses`` list and returns
        a context manager yielding a ``MockLLM`` instance.
    """
    @contextmanager
    def _env(responses: list[str] | None = None) -> Any:
        class MockLLMResponse:
            def __init__(self, content: str):
                self.content = content

        class MockLLM:
            def __init__(self, resp: list[str]):
                self.responses = resp
                self._idx = 0
                self.call_count = 0

            def invoke(self, *args: Any, **kwargs: Any) -> MockLLMResponse:
                resp = self.responses[self._idx % len(self.responses)]
                self._idx += 1
                self.call_count += 1
                return MockLLMResponse(resp)

            def __call__(self, *args: Any, **kwargs: Any) -> MockLLMResponse:
                return self.invoke(*args, **kwargs)

        mock = MockLLM(responses or ["mock response"])
        try:
            yield mock
        finally:
            pass

    return _env
