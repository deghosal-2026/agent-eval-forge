"""Tests for evalforge.testing.fixtures — LangGraph and LLM mock fixtures."""

from __future__ import annotations

pytest_plugins = ["evalforge.testing.fixtures"]


def _thread_config(thread_id: str = "test-1") -> dict:
    return {"configurable": {"thread_id": thread_id}}


class TestCompiledGraphWithMemory:
    def test_graph_is_compiled_state_graph(
        self, compiled_graph_with_memory: object,
    ) -> None:
        from langgraph.graph.state import CompiledStateGraph

        assert isinstance(compiled_graph_with_memory, CompiledStateGraph)

    def test_graph_invocation_runs_echo_and_process(
        self, compiled_graph_with_memory: object,
    ) -> None:
        result = compiled_graph_with_memory.invoke(
            {"input": "hello"}, _thread_config(),
        )

        assert result["echoed"] == "hello"
        assert result["processed"] == "processed:hello"
        assert result["node_history"] == ["echo", "process"]

    def test_graph_with_empty_input(
        self, compiled_graph_with_memory: object,
    ) -> None:
        result = compiled_graph_with_memory.invoke(
            {"input": ""}, _thread_config(),
        )

        assert result["echoed"] == ""
        assert result["processed"] == "processed:"
        assert result["node_history"] == ["echo", "process"]

    def test_graph_node_history_initialized_when_missing(
        self, compiled_graph_with_memory: object,
    ) -> None:
        result = compiled_graph_with_memory.invoke(
            {"input": "x"}, _thread_config(),
        )

        assert result["node_history"] == ["echo", "process"]

    def test_graph_checkpoint_persists_state(
        self, compiled_graph_with_memory: object,
    ) -> None:
        config = _thread_config("checkpoint-1")
        compiled_graph_with_memory.invoke({"input": "first"}, config)
        state = compiled_graph_with_memory.get_state(config)

        assert state.values["input"] == "first"
        assert state.values["echoed"] == "first"
        assert state.values["processed"] == "processed:first"
        assert state.values["node_history"] == ["echo", "process"]

    def test_graph_separate_threads_independent_checkpoints(
        self, compiled_graph_with_memory: object,
    ) -> None:
        cf1 = _thread_config("t-a")
        compiled_graph_with_memory.invoke({"input": "a1"}, cf1)

        cf2 = _thread_config("t-b")
        result = compiled_graph_with_memory.invoke({"input": "b1"}, cf2)

        assert result["node_history"] == ["echo", "process"]


class TestNodeMockEnv:
    def test_env_is_callable(self, node_mock_env: object) -> None:
        assert callable(node_mock_env)

    def test_default_responses_when_no_args(self, node_mock_env: object) -> None:
        with node_mock_env() as mock:
            r = mock.invoke("any prompt")
            assert r.content == "mock response"
            assert mock.call_count == 1

    def test_default_responses_when_none_explicit(
        self, node_mock_env: object,
    ) -> None:
        with node_mock_env(responses=None) as mock:
            r = mock.invoke("any prompt")
            assert r.content == "mock response"

    def test_custom_single_response(self, node_mock_env: object) -> None:
        with node_mock_env(responses=["explicit"]) as mock:
            r = mock.invoke("prompt")
            assert r.content == "explicit"

    def test_custom_multiple_responses_cycle(
        self, node_mock_env: object,
    ) -> None:
        with node_mock_env(responses=["a", "b", "c"]) as mock:
            assert mock.invoke("").content == "a"
            assert mock.invoke("").content == "b"
            assert mock.invoke("").content == "c"
            assert mock.invoke("").content == "a"
            assert mock.call_count == 4

    def test_call_delegates_to_invoke(self, node_mock_env: object) -> None:
        with node_mock_env(responses=["via call"]) as mock:
            r = mock("some prompt")
            assert r.content == "via call"
            assert mock.call_count == 1

    def test_call_and_invoke_share_call_count(
        self, node_mock_env: object,
    ) -> None:
        with node_mock_env(responses=["x", "y"]) as mock:
            mock.invoke("p1")
            mock("p2")
            assert mock.call_count == 2

    def test_call_count_starts_at_zero(self, node_mock_env: object) -> None:
        with node_mock_env(responses=["r"]) as mock:
            assert mock.call_count == 0
            mock.invoke("")
            assert mock.call_count == 1

    def test_empty_list_falls_back_to_default(
        self, node_mock_env: object,
    ) -> None:
        with node_mock_env(responses=[]) as mock:
            r = mock.invoke("")
            assert r.content == "mock response"

    def test_mock_llm_response_has_content(self, node_mock_env: object) -> None:
        with node_mock_env(responses=["content check"]) as mock:
            r = mock.invoke("")
            assert r.content == "content check"
            assert hasattr(r, "content")

    def test_env_can_be_stored_and_reused(self, node_mock_env: object) -> None:
        factory = node_mock_env
        with factory(responses=["stored"]) as mock:
            assert mock.invoke("").content == "stored"
