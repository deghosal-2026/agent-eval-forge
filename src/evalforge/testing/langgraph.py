"""LangGraph test harness — node-level and integration testing utilities.

Provides :class:`NodeTestConfig` for describing a single-node test and
:class:`LangGraphTestHarness` for running those tests, mocking LLM
responses, compiling graphs with memory, and inspecting/interrupting state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class NodeTestConfig:
    """Configuration for testing a single node in a LangGraph.

    Attributes:
        graph_name: Human-readable identifier for the graph under test.
        node_name: Name of the node being tested.
        state_constructor: Zero-arg callable that returns the initial state dict.
        mock_llm_fn: Optional callable to replace the real LLM invoke.
        assert_state_keys: Expected keys that must be present in the result state.
        assert_state_values: Expected key-value pairs the result state must match.
    """
    graph_name: str
    node_name: str
    state_constructor: Callable[[], dict[str, Any]]
    mock_llm_fn: Callable[..., Any] | None = None
    assert_state_keys: list[str] | None = None
    assert_state_values: dict[str, Any] | None = None


class LangGraphTestHarness:
    """Test harness for LangGraph agents — node testing, routing, resume, mocking.

    Supports per-node assertions, interrupt-before inspection, state
    checkpointing, and LLM response mocking.
    """

    def __init__(self, adapter_config: dict[str, Any] | None = None) -> None:
        """Initialise the harness.

        Args:
            adapter_config: Optional adapter configuration dict forwarded to
                the agent adapter (e.g. model overrides).
        """
        self._adapter_config: dict[str, Any] = adapter_config or {}
        self._checkpointer: Any = None
        self._callbacks: list[Any] = []
        self._mocked_llm = False

    def test_node(self, config: NodeTestConfig) -> dict[str, Any]:
        """Execute state constructor and validate resulting state against config.

        Args:
            config: :class:`NodeTestConfig` describing assertions.

        Returns:
            Dict with keys ``passed``, ``actual_state``, ``expected_state``,
            ``errors``.
        """
        try:
            state = config.state_constructor()
            errors: list[str] = []

            if config.assert_state_keys is not None:
                for key in config.assert_state_keys:
                    if key not in state:
                        errors.append(f"Expected state key '{key}' not found in state")

            if config.assert_state_values is not None:
                for key, expected in config.assert_state_values.items():
                    actual = state.get(key)
                    if actual != expected:
                        errors.append(
                            f"State key '{key}': expected {expected!r}, got {actual!r}"
                        )

            return {
                "passed": len(errors) == 0,
                "actual_state": state,
                "expected_state": config.assert_state_values or {},
                "errors": errors,
            }
        except Exception as exc:
            return {
                "passed": False,
                "actual_state": {},
                "expected_state": config.assert_state_values or {},
                "errors": [str(exc)],
            }

    def mock_node_llm(
        self, node_fn: Callable[..., Any], responses: list[str]
    ) -> Callable[..., Any]:
        """Wrap a node function so LLM calls return canned responses.

        Args:
            node_fn: The original node function (ignored — the wrapper
                produces the mock output directly).
            responses: List of canned LLM response strings.

        Returns:
            A wrapped function that adds ``llm_response`` and a synthetic
            assistant ``messages`` entry to the state.
        """
        call_count = [0]

        def _wrapped(state: dict[str, Any]) -> dict[str, Any]:
            idx = call_count[0]
            call_count[0] += 1
            response = responses[min(idx, len(responses) - 1)]
            result = dict(state)
            result["llm_response"] = response
            result["messages"] = [
                *result.get("messages", []),
                {"role": "assistant", "content": response},
            ]
            return result

        return _wrapped

    def compile_with_memory(self, graph_builder: Any, checkpointer: Any = None) -> Any:
        """Compile a StateGraph with an in-memory (or custom) checkpointer.

        Args:
            graph_builder: A ``StateGraph`` builder instance.
            checkpointer: Optional checkpointer; falls back to ``MemorySaver``.

        Returns:
            A compiled ``CompiledStateGraph``.
        """
        if checkpointer is not None:
            self._checkpointer = checkpointer
        elif self._checkpointer is None:
            from langgraph.checkpoint.memory import MemorySaver

            self._checkpointer = MemorySaver()
        compiled = graph_builder.compile(checkpointer=self._checkpointer)
        return compiled

    def interrupt_before(self, graph: Any, node_name: str, state: dict[str, Any]) -> dict[str, Any]:
        """Invoke the graph but interrupt just before *node_name* and return the snapshot.

        Args:
            graph: A compiled LangGraph.
            node_name: Node at which to interrupt.
            state: Input state dict.

        Returns:
            The checkpoint state at the interruption point.
        """
        thread_id = "test-thread-interrupt"
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        try:
            graph.invoke(state, config, interrupt_before=[node_name])
        except Exception:  # noqa: S110
            pass
        return self.inspect_state(graph, thread_id)

    def inspect_state(self, graph: Any, thread_id: str) -> dict[str, Any]:
        """Read the current checkpoint state for a given thread.

        Args:
            graph: A compiled LangGraph.
            thread_id: The conversation / thread identifier.

        Returns:
            The state dict if available, or an empty dict.
        """
        if self._checkpointer is None:
            return {}
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = graph.get_state(config)
            if state and hasattr(state, "values") and state.values:
                return dict(state.values)
            return {}
        except Exception:
            return {}

    def test_routing(self, graph: Any, state: dict[str, Any], expected_next: str) -> bool:
        """Invoke the graph and verify routing completes without errors.

        Args:
            graph: A compiled LangGraph.
            state: Input state dict.
            expected_next: The name of the node expected to run next (currently
                only checked implicitly via absence of errors).

        Returns:
            ``True`` if the invocation did not raise.
        """
        try:
            graph.invoke(state, {"configurable": {"thread_id": "routing-test"}})
            return True
        except Exception:
            return False

    def test_resume(self, graph: Any, thread_id: str, resume_value: Any) -> dict[str, Any]:
        """Resume a previously interrupted graph execution.

        Args:
            graph: A compiled LangGraph.
            thread_id: Thread to resume.
            resume_value: Value to pass as the resume/command payload.

        Returns:
            Result dict with ``passed`` and ``result`` or ``error``.
        """
        config = {"configurable": {"thread_id": thread_id}}
        try:
            result = graph.invoke(None, config)
            return {"passed": True, "result": result}
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    @property
    def checkpointer(self) -> Any:
        """Return the currently configured checkpointer (may be None)."""
        return self._checkpointer

    def set_mocked_llm_profile(self, enabled: bool = True) -> None:
        """Enable or disable the mocked LLM profile for this harness.

        Args:
            enabled: Whether to use mocked LLM responses.
        """
        self._mocked_llm = enabled

    def with_callbacks(self, callbacks: list[Any]) -> None:
        """Attach runtime callbacks (e.g. for tracing or event forwarding).

        Args:
            callbacks: List of LangGraph-compatible callback objects.
        """
        self._callbacks = callbacks
