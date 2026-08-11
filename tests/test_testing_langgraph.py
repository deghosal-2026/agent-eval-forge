"""Tests for ``evalforge.testing.langgraph`` — LangGraph test harness."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from evalforge.testing.langgraph import (
    LangGraphTestHarness,
    NodeTestConfig,
)


class TestNodeTestConfig:
    """Tests for NodeTestConfig dataclass."""

    def test_minimal_config(self) -> None:
        def state_fn():
            return {"key": "val"}
        config = NodeTestConfig(
            graph_name="test_graph",
            node_name="test_node",
            state_constructor=state_fn,
        )
        assert config.graph_name == "test_graph"
        assert config.node_name == "test_node"
        assert config.state_constructor is state_fn
        assert config.mock_llm_fn is None
        assert config.assert_state_keys is None
        assert config.assert_state_values is None

    def test_full_config(self) -> None:
        def state_fn():
            return {"key": "val"}
        def mock_fn():
            return "mock"
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=state_fn,
            mock_llm_fn=mock_fn,
            assert_state_keys=["key"],
            assert_state_values={"key": "val"},
        )
        assert config.graph_name == "g"
        assert config.node_name == "n"
        assert config.state_constructor is state_fn
        assert config.mock_llm_fn is mock_fn
        assert config.assert_state_keys == ["key"]
        assert config.assert_state_values == {"key": "val"}


class TestLangGraphTestHarnessInit:
    """Tests for LangGraphTestHarness.__init__."""

    def test_default_init(self) -> None:
        harness = LangGraphTestHarness()
        assert harness._adapter_config == {}
        assert harness._checkpointer is None
        assert harness._callbacks == []
        assert harness._mocked_llm is False

    def test_init_with_adapter_config(self) -> None:
        config = {"model": "gpt-4", "temperature": 0}
        harness = LangGraphTestHarness(adapter_config=config)
        assert harness._adapter_config == config
        assert harness._checkpointer is None
        assert harness._callbacks == []


class TestLangGraphTestHarnessTestNode:
    """Tests for LangGraphTestHarness.test_node."""

    def test_node_passes_all_assertions(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {"a": 1, "b": 2},
            assert_state_keys=["a", "b"],
            assert_state_values={"a": 1, "b": 2},
        )
        result = harness.test_node(config)
        assert result["passed"] is True
        assert result["actual_state"] == {"a": 1, "b": 2}
        assert result["expected_state"] == {"a": 1, "b": 2}
        assert result["errors"] == []

    def test_node_fails_missing_state_key(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {"a": 1},
            assert_state_keys=["a", "b"],
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert result["actual_state"] == {"a": 1}
        assert "Expected state key 'b' not found in state" in result["errors"]

    def test_node_fails_mismatched_value(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {"a": 1},
            assert_state_values={"a": 999},
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert "State key 'a': expected 999, got 1" in result["errors"]

    def test_node_passes_with_only_key_assertions(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {"x": 10},
            assert_state_keys=["x"],
        )
        result = harness.test_node(config)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_node_passes_with_only_value_assertions(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {"x": 10},
            assert_state_values={"x": 10},
        )
        result = harness.test_node(config)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_node_passes_with_no_assertions(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {"x": 10},
        )
        result = harness.test_node(config)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_node_handles_state_constructor_exception(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: (_ for _ in ()).throw(ValueError("boom")),
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert result["actual_state"] == {}
        assert "boom" in result["errors"][0]

    def test_node_state_value_missing_key_defaults_to_none(self) -> None:
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="g",
            node_name="n",
            state_constructor=lambda: {},
            assert_state_values={"missing_key": "expected"},
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert "State key 'missing_key': expected 'expected', got None" in result["errors"]


class TestLangGraphTestHarnessMockNodeLLM:
    """Tests for LangGraphTestHarness.mock_node_llm."""

    def test_first_call_returns_first_response(self) -> None:
        harness = LangGraphTestHarness()
        wrapped = harness.mock_node_llm(lambda s: s, ["hello"])
        result = wrapped({"existing": "key"})
        assert result["llm_response"] == "hello"
        assert result["existing"] == "key"
        assert result["messages"] == [{"role": "assistant", "content": "hello"}]

    def test_multiple_calls_cycle_responses(self) -> None:
        harness = LangGraphTestHarness()
        wrapped = harness.mock_node_llm(lambda s: s, ["first", "second", "third"])
        r1 = wrapped({})
        r2 = wrapped({})
        r3 = wrapped({})
        assert r1["llm_response"] == "first"
        assert r2["llm_response"] == "second"
        assert r3["llm_response"] == "third"

    def test_exceeds_responses_list_repeats_last(self) -> None:
        harness = LangGraphTestHarness()
        wrapped = harness.mock_node_llm(lambda s: s, ["only"])
        r1 = wrapped({})
        r2 = wrapped({})
        r3 = wrapped({})
        assert r1["llm_response"] == "only"
        assert r2["llm_response"] == "only"
        assert r3["llm_response"] == "only"

    def test_appends_to_existing_messages(self) -> None:
        harness = LangGraphTestHarness()
        existing = {"messages": [{"role": "user", "content": "hi"}]}
        wrapped = harness.mock_node_llm(lambda s: s, ["response1"])
        result = wrapped(existing)
        assert result["messages"] == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "response1"},
        ]

    def test_preserves_all_original_state_keys(self) -> None:
        harness = LangGraphTestHarness()
        original = {"a": 1, "b": 2, "messages": []}
        wrapped = harness.mock_node_llm(lambda s: s, ["r"])
        result = wrapped(original)
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["llm_response"] == "r"

    def test_ignores_node_fn_parameter(self) -> None:
        harness = LangGraphTestHarness()
        called = []

        def real_node(state: dict) -> dict:
            called.append(state)
            return state

        wrapped = harness.mock_node_llm(real_node, ["mock"])
        result = wrapped({"x": 1})
        assert len(called) == 0
        assert result["llm_response"] == "mock"


class TestLangGraphTestHarnessCompileWithMemory:
    """Tests for LangGraphTestHarness.compile_with_memory."""

    def test_compile_uses_fallback_memory_saver(self) -> None:
        harness = LangGraphTestHarness()
        mock_builder = MagicMock()
        mock_compiled = MagicMock()
        mock_memory_saver = MagicMock()

        mock_checkpoint = ModuleType("langgraph.checkpoint")
        mock_memory = ModuleType("langgraph.checkpoint.memory")
        mock_memory.MemorySaver = MagicMock(return_value=mock_memory_saver)

        with patch.dict(sys.modules, {
            "langgraph": ModuleType("langgraph"),
            "langgraph.checkpoint": mock_checkpoint,
            "langgraph.checkpoint.memory": mock_memory,
        }):
            mock_builder.compile.return_value = mock_compiled
            result = harness.compile_with_memory(mock_builder)

        assert result is mock_compiled
        mock_builder.compile.assert_called_once()
        assert harness._checkpointer is not None

    def test_compile_with_custom_checkpointer(self) -> None:
        harness = LangGraphTestHarness()
        mock_builder = MagicMock()
        mock_compiled = MagicMock()
        custom_checkpointer = MagicMock()

        mock_builder.compile.return_value = mock_compiled
        result = harness.compile_with_memory(mock_builder, checkpointer=custom_checkpointer)

        assert result is mock_compiled
        mock_builder.compile.assert_called_once_with(checkpointer=custom_checkpointer)
        assert harness._checkpointer is custom_checkpointer

    def test_compile_reuses_existing_checkpointer(self) -> None:
        harness = LangGraphTestHarness()
        mock_builder = MagicMock()
        mock_compiled = MagicMock()
        existing_checkpointer = MagicMock()
        harness._checkpointer = existing_checkpointer

        mock_builder.compile.return_value = mock_compiled
        result = harness.compile_with_memory(mock_builder)

        assert result is mock_compiled
        mock_builder.compile.assert_called_once_with(checkpointer=existing_checkpointer)


class TestLangGraphTestHarnessInterruptBefore:
    """Tests for LangGraphTestHarness.interrupt_before."""

    def test_interrupt_returns_state_snapshot(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = Exception("interrupted")
        expected_state = {"key": "checkpoint_value"}
        harness._checkpointer = MagicMock()

        def inspect_state(graph, thread_id):
            return expected_state

        harness.inspect_state = inspect_state  # type: ignore[method-assign]

        result = harness.interrupt_before(mock_graph, "my_node", {"input": "data"})
        assert result == expected_state

    def test_interrupt_calls_graph_with_correct_args(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = Exception("interrupted")
        harness._checkpointer = MagicMock()

        def inspect_state(graph, thread_id):
            return {}

        harness.inspect_state = inspect_state  # type: ignore[method-assign]

        harness.interrupt_before(mock_graph, "critical_node", {"x": 1})
        call_args = mock_graph.invoke.call_args
        assert call_args.args[0] == {"x": 1}
        assert call_args.kwargs["interrupt_before"] == ["critical_node"]


class TestLangGraphTestHarnessInspectState:
    """Tests for LangGraphTestHarness.inspect_state."""

    def test_inspect_returns_empty_when_no_checkpointer(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        result = harness.inspect_state(mock_graph, "thread-1")
        assert result == {}

    def test_inspect_returns_state_when_available(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_state = MagicMock()
        mock_state.values = {"a": 1, "b": 2}
        mock_graph.get_state.return_value = mock_state
        harness._checkpointer = MagicMock()

        result = harness.inspect_state(mock_graph, "thread-1")
        assert result == {"a": 1, "b": 2}
        mock_graph.get_state.assert_called_once_with(
            {"configurable": {"thread_id": "thread-1"}}
        )

    def test_inspect_returns_empty_when_state_is_none(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.get_state.return_value = None
        harness._checkpointer = MagicMock()

        result = harness.inspect_state(mock_graph, "thread-1")
        assert result == {}

    def test_inspect_returns_empty_when_state_has_no_values(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_state = MagicMock()
        del mock_state.values
        harness._checkpointer = MagicMock()
        mock_graph.get_state.return_value = mock_state

        result = harness.inspect_state(mock_graph, "thread-1")
        assert result == {}

    def test_inspect_returns_empty_when_values_is_none(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_state = MagicMock()
        mock_state.values = None
        harness._checkpointer = MagicMock()
        mock_graph.get_state.return_value = mock_state

        result = harness.inspect_state(mock_graph, "thread-1")
        assert result == {}

    def test_inspect_returns_empty_on_exception(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.get_state.side_effect = RuntimeError("state error")
        harness._checkpointer = MagicMock()

        result = harness.inspect_state(mock_graph, "thread-1")
        assert result == {}


class TestLangGraphTestHarnessTestRouting:
    """Tests for LangGraphTestHarness.test_routing."""

    def test_routing_returns_true_on_success(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "ok"}
        result = harness.test_routing(mock_graph, {"input": "hi"}, "next_node")
        assert result is True

    def test_routing_returns_false_on_exception(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("graph error")
        result = harness.test_routing(mock_graph, {"input": "hi"}, "next_node")
        assert result is False

    def test_routing_passes_thread_id_config(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "ok"}
        harness.test_routing(mock_graph, {"x": 1}, "destination")
        call_args = mock_graph.invoke.call_args
        assert call_args.args[0] == {"x": 1}
        assert call_args.kwargs.get("configurable", None) is not None or \
            call_args.args[1]["configurable"]["thread_id"] == "routing-test"


class TestLangGraphTestHarnessTestResume:
    """Tests for LangGraphTestHarness.test_resume."""

    def test_resume_returns_passed_true_on_success(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        expected_result = {"final_state": "done"}
        mock_graph.invoke.return_value = expected_result
        result = harness.test_resume(mock_graph, "thread-99", None)
        assert result["passed"] is True
        assert result["result"] == expected_result

    def test_resume_invokes_with_none_and_correct_config(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"ok": True}
        harness.test_resume(mock_graph, "resume-thread", None)
        call_args = mock_graph.invoke.call_args
        assert call_args.args[0] is None
        assert call_args.args[1]["configurable"]["thread_id"] == "resume-thread"

    def test_resume_returns_passed_false_on_exception(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("resume failed")
        result = harness.test_resume(mock_graph, "thread-99", None)
        assert result["passed"] is False
        assert "resume failed" in result["error"]

    def test_resume_accepts_resume_value_parameter(self) -> None:
        harness = LangGraphTestHarness()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"ok": True}
        result = harness.test_resume(mock_graph, "t", {"command": "continue"})
        assert result["passed"] is True


class TestLangGraphTestHarnessCheckpointer:
    """Tests for LangGraphTestHarness.checkpointer property."""

    def test_checkpointer_returns_none_initially(self) -> None:
        harness = LangGraphTestHarness()
        assert harness.checkpointer is None

    def test_checkpointer_returns_set_value(self) -> None:
        harness = LangGraphTestHarness()
        cp = MagicMock()
        harness._checkpointer = cp
        assert harness.checkpointer is cp


class TestLangGraphTestHarnessSetMockedLLMProfile:
    """Tests for LangGraphTestHarness.set_mocked_llm_profile."""

    def test_enable_mocked_llm(self) -> None:
        harness = LangGraphTestHarness()
        assert harness._mocked_llm is False
        harness.set_mocked_llm_profile(enabled=True)
        assert harness._mocked_llm is True

    def test_disable_mocked_llm(self) -> None:
        harness = LangGraphTestHarness()
        harness.set_mocked_llm_profile(enabled=True)
        assert harness._mocked_llm is True
        harness.set_mocked_llm_profile(enabled=False)
        assert harness._mocked_llm is False

    def test_default_enabled_is_true(self) -> None:
        harness = LangGraphTestHarness()
        harness.set_mocked_llm_profile()
        assert harness._mocked_llm is True


class TestLangGraphTestHarnessWithCallbacks:
    """Tests for LangGraphTestHarness.with_callbacks."""

    def test_with_callbacks_sets_list(self) -> None:
        harness = LangGraphTestHarness()
        cb1 = MagicMock()
        cb2 = MagicMock()
        harness.with_callbacks([cb1, cb2])
        assert harness._callbacks == [cb1, cb2]

    def test_with_callbacks_overwrites_previous(self) -> None:
        harness = LangGraphTestHarness()
        harness.with_callbacks([MagicMock()])
        new_cb = MagicMock()
        harness.with_callbacks([new_cb])
        assert harness._callbacks == [new_cb]

    def test_with_callbacks_empty_list(self) -> None:
        harness = LangGraphTestHarness()
        harness.with_callbacks([MagicMock()])
        harness.with_callbacks([])
        assert harness._callbacks == []
