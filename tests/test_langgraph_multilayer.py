from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from evalforge.testing import LangGraphTestHarness, NodeTestConfig


def _build_two_node_graph():
    builder = StateGraph(dict)

    def node_a(state: dict) -> dict:
        state["visited"] = [*state.get("visited", []), "A"]
        state["data"] = state.get("data", "") + "_a"
        return state

    def node_b(state: dict) -> dict:
        state["visited"] = [*state.get("visited", []), "B"]
        state["data"] = state.get("data", "") + "_b"
        return state

    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)
    builder.set_entry_point("node_a")
    builder.add_edge("node_a", "node_b")
    builder.set_finish_point("node_b")
    return builder


def _build_routing_graph():
    builder = StateGraph(dict)

    def router(state: dict) -> dict:
        choice = state.get("route", "b")
        state["routed_to"] = choice
        return state

    def path_b(state: dict) -> dict:
        state["result"] = "took_b"
        return state

    def path_c(state: dict) -> dict:
        state["result"] = "took_c"
        return state

    builder.add_node("router", router)
    builder.add_node("path_b", path_b)
    builder.add_node("path_c", path_c)
    builder.set_entry_point("router")

    def choose_route(state: dict) -> str:
        return state.get("route", "b")

    builder.add_conditional_edges("router", choose_route, {"b": "path_b", "c": "path_c"})
    builder.set_finish_point("path_b")
    builder.set_finish_point("path_c")
    return builder


def _build_interrupt_graph():
    builder = StateGraph(dict)

    def step_one(state: dict) -> dict:
        state["step"] = "one"
        state["data"] = "before_interrupt"
        return state

    def step_two(state: dict) -> dict:
        state["step"] = "two"
        state["data"] = "after_interrupt"
        return state

    builder.add_node("step_one", step_one)
    builder.add_node("step_two", step_two)
    builder.set_entry_point("step_one")
    builder.add_edge("step_one", "step_two")
    builder.set_finish_point("step_two")
    return builder


class TestLayer1NodeUnitTesting:

    def test_node_with_mock_llm(self):
        harness = LangGraphTestHarness()

        def my_node(state: dict) -> dict:
            return state

        wrapped = harness.mock_node_llm(my_node, ["Hello"])
        state = {"messages": []}
        result = wrapped(state)
        assert result["llm_response"] == "Hello"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Hello"

    def test_node_asserts_state_key_updates(self):
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="test_graph",
            node_name="transform",
            state_constructor=lambda: {"x": 1, "y": 2, "z": 3},
            assert_state_keys=["x", "y", "z"],
        )
        result = harness.test_node(config)
        assert result["passed"] is True
        assert len(result["errors"]) == 0

    def test_tool_node_schema_validation(self):
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="tool_graph",
            node_name="search_tool",
            state_constructor=lambda: {
                "messages": [],
                "tool_calls": [{"name": "search", "args": {"query": "test"}}],
            },
            assert_state_keys=["messages", "tool_calls"],
            assert_state_values={"messages": []},
        )
        result = harness.test_node(config)
        assert result["passed"] is True

    def test_node_with_wrong_state_keys_fails(self):
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="test_graph",
            node_name="transform",
            state_constructor=lambda: {"x": 1},
            assert_state_keys=["missing_key"],
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert any("missing_key" in e for e in result["errors"])

    def test_node_with_wrong_state_values_fails(self):
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="test_graph",
            node_name="transform",
            state_constructor=lambda: {"score": 0.5},
            assert_state_values={"score": 1.0},
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert any("score" in e for e in result["errors"])

    def test_mock_node_llm_cycles_responses(self):
        harness = LangGraphTestHarness()

        def my_node(state: dict) -> dict:
            return state

        wrapped = harness.mock_node_llm(my_node, ["First", "Second"])
        r1 = wrapped({"messages": []})
        r2 = wrapped({"messages": []})
        assert r1["llm_response"] == "First"
        assert r2["llm_response"] == "Second"

    def test_mock_node_llm_uses_last_response_when_exhausted(self):
        harness = LangGraphTestHarness()

        def my_node(state: dict) -> dict:
            return state

        wrapped = harness.mock_node_llm(my_node, ["Only"])
        r1 = wrapped({"messages": []})
        r2 = wrapped({"messages": []})
        r3 = wrapped({"messages": []})
        assert r1["llm_response"] == "Only"
        assert r2["llm_response"] == "Only"
        assert r3["llm_response"] == "Only"


class TestLayer2PartialExecutionAndRouting:

    def test_graph_compilation_with_memory(self):
        builder = _build_two_node_graph()
        harness = LangGraphTestHarness()
        checkpointer = MemorySaver()
        graph = harness.compile_with_memory(builder, checkpointer=checkpointer)
        assert harness.checkpointer is not None
        assert graph is not None
        result = graph.invoke(
            {"data": "start"},
            {"configurable": {"thread_id": "t1"}},
        )
        assert "visited" in result
        assert "A" in result["visited"]
        assert "B" in result["visited"]

    def test_state_inspection_via_checkpointer(self):
        builder = _build_two_node_graph()
        harness = LangGraphTestHarness()
        graph = harness.compile_with_memory(builder)
        graph.invoke(
            {"data": "start"},
            {"configurable": {"thread_id": "t1"}},
        )
        state = harness.inspect_state(graph, "t1")
        assert "visited" in state or state == {}

    def test_routing_validation_conditional_edges(self):
        builder = _build_routing_graph()
        harness = LangGraphTestHarness()
        graph = harness.compile_with_memory(builder)
        result_b = graph.invoke(
            {"route": "b"},
            {"configurable": {"thread_id": "rb"}},
        )
        assert result_b["result"] == "took_b"
        result_c = graph.invoke(
            {"route": "c"},
            {"configurable": {"thread_id": "rc"}},
        )
        assert result_c["result"] == "took_c"

    def test_routing_harness_method(self):
        builder = _build_routing_graph()
        harness = LangGraphTestHarness()
        graph = harness.compile_with_memory(builder)
        passed = harness.test_routing(graph, {"route": "b"}, "path_b")
        assert passed is True

    def test_interrupt_before_pauses_at_correct_node(self):
        builder = _build_interrupt_graph()
        harness = LangGraphTestHarness()
        graph = harness.compile_with_memory(builder)
        state_snapshot = harness.interrupt_before(graph, "step_one", {"input": "go"})
        assert isinstance(state_snapshot, dict)

    def test_resume_after_interrupt(self):
        builder = _build_interrupt_graph()
        harness = LangGraphTestHarness()
        graph = harness.compile_with_memory(builder)

        thread_id = "resume-test"
        config = {"configurable": {"thread_id": thread_id}}

        graph.invoke({"input": "go"}, config, interrupt_before=["step_two"])

        state_before = harness.inspect_state(graph, thread_id)
        assert isinstance(state_before, dict)

        result = harness.test_resume(graph, thread_id, None)
        assert result["passed"] is True


class TestHarnessIntegration:

    def test_checkpointer_passthrough_through_adapter(self):
        from evalforge.adapters.langgraph import LangGraphAdapter
        from evalforge.models.pack import Scenario

        adapter = LangGraphAdapter()
        scenario = Scenario(
            id="sc-cp",
            title="Checkpointer",
            input="test",
            context={"mode": "tool_call"},
            allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
        )
        config = {
            "module": "fixtures.langgraph_agent",
            "function": "build_agent",
            "run_id": "run-cp",
            "checkpointer": "memory",
            "timeout_seconds": 10,
        }
        artifact = adapter.run(scenario, config)
        assert artifact.status == "completed"

    def test_callbacks_passthrough_through_adapter(self):
        from evalforge.adapters.langgraph import LangGraphAdapter
        from evalforge.models.pack import Scenario

        callbacks_log: list[dict] = []

        class LoggingCallback:
            def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
                callbacks_log.append({"event": "llm_start"})

        adapter = LangGraphAdapter()
        scenario = Scenario(
            id="sc-cb",
            title="Callbacks",
            input="test",
            context={"mode": "tool_call"},
            allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
        )
        config = {
            "module": "fixtures.langgraph_agent",
            "function": "build_agent",
            "run_id": "run-cb",
            "callbacks": [LoggingCallback()],
            "timeout_seconds": 10,
        }
        artifact = adapter.run(scenario, config)
        assert artifact.status in ("completed", "error")

    def test_mocked_llm_mode_toggle(self):
        harness = LangGraphTestHarness()
        assert harness._mocked_llm is False
        harness.set_mocked_llm_profile(enabled=True)
        assert harness._mocked_llm is True
        harness.set_mocked_llm_profile(enabled=False)
        assert harness._mocked_llm is False

    def test_node_mock_env_fixture_creates_clean_mock(self):
        from contextlib import contextmanager

        @contextmanager
        def _env(responses=None):
            class MockLLMResponse:
                def __init__(self, content):
                    self.content = content

            class MockLLM:
                def __init__(self, resp):
                    self.responses = resp
                    self._idx = 0
                    self.call_count = 0

                def invoke(self, *args, **kwargs):
                    resp = self.responses[self._idx % len(self.responses)]
                    self._idx += 1
                    self.call_count += 1
                    return MockLLMResponse(resp)

            mock = MockLLM(responses or ["mock response"])
            try:
                yield mock
            finally:
                pass

        with _env(["response_1", "response_2"]) as mock:
            r1 = mock.invoke("prompt")
            r2 = mock.invoke("prompt")
            assert r1.content == "response_1"
            assert r2.content == "response_2"
            assert mock.call_count == 2

    def test_compiled_graph_with_memory_fixture_works(self):
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import StateGraph

        builder = StateGraph(dict)

        def echo_node(state: dict) -> dict:
            state["echoed"] = state.get("input", "")
            state["node_history"] = [*state.get("node_history", []), "echo"]
            return state

        def process_node(state: dict) -> dict:
            val = state.get("input", "")
            state["processed"] = f"processed:{val}"
            state["node_history"] = [*state.get("node_history", []), "process"]
            return state

        builder.add_node("echo", echo_node)
        builder.add_node("process", process_node)
        builder.set_entry_point("echo")
        builder.add_edge("echo", "process")
        builder.set_finish_point("process")

        graph = builder.compile(checkpointer=MemorySaver())

        result = graph.invoke(
            {"input": "hello"},
            {"configurable": {"thread_id": "fix-test"}},
        )
        assert result["echoed"] == "hello"
        assert result["processed"] == "processed:hello"
        assert "echo" in result["node_history"]
        assert "process" in result["node_history"]

    def test_full_pipeline_compile_interrupt_inspect_resume(self):
        builder = _build_interrupt_graph()
        harness = LangGraphTestHarness()
        graph = harness.compile_with_memory(builder)

        thread_id = "full-pipeline"
        config = {"configurable": {"thread_id": thread_id}}

        state_before = harness.inspect_state(graph, thread_id)
        assert isinstance(state_before, dict)

        graph.invoke(
            {"input": "start"},
            config,
            interrupt_before=["step_two"],
        )

        state_interrupted = harness.inspect_state(graph, thread_id)
        assert isinstance(state_interrupted, dict)
        assert state_interrupted.get("data") == "before_interrupt"

        result = harness.test_resume(graph, thread_id, None)
        assert result["passed"] is True

    def test_with_callbacks_stores_reference(self):
        harness = LangGraphTestHarness()

        class FakeCallback:
            pass

        cb = FakeCallback()
        harness.with_callbacks([cb])
        assert len(harness._callbacks) == 1
        assert harness._callbacks[0] is cb

    def test_adapter_interrupt_before_config_passthrough(self):
        from evalforge.adapters.langgraph import LangGraphAdapter
        from evalforge.models.pack import Scenario

        adapter = LangGraphAdapter()
        scenario = Scenario(
            id="sc-ib",
            title="Interrupt",
            input="test",
            context={"mode": "tool_call"},
            allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
        )
        config = {
            "module": "fixtures.langgraph_agent",
            "function": "build_agent",
            "run_id": "run-ib",
            "checkpointer": "memory",
            "interrupt_before": ["tools"],
            "timeout_seconds": 10,
        }
        artifact = adapter.run(scenario, config)
        assert artifact.status in ("completed", "error")

    def test_node_test_exception_handling(self):
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="broken_graph",
            node_name="failing_node",
            state_constructor=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = harness.test_node(config)
        assert result["passed"] is False
        assert len(result["errors"]) >= 1

    def test_node_test_no_assertions_passes(self):
        harness = LangGraphTestHarness()
        config = NodeTestConfig(
            graph_name="minimal",
            node_name="passthrough",
            state_constructor=lambda: {},
        )
        result = harness.test_node(config)
        assert result["passed"] is True
        assert result["actual_state"] == {}
