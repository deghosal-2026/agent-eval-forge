"""Tests for LangGraph VCR replay, node timing, and DeepEval integration.

Layers 3 & 4 of the multi-layer validation framework.
"""

import json
import time
from pathlib import Path

import pytest

from evalforge.testing.deepeval import DeepEvalIntegration
from evalforge.testing.timing import NodeTiming, TimingCollector
from evalforge.testing.vcr import LLMVCR, LLMCassette


class TestLLMCassette:
    def test_create_empty_cassette(self) -> None:
        cassette = LLMCassette(name="test")
        assert cassette.name == "test"
        assert cassette.interactions == []

    def test_cassette_with_interactions(self) -> None:
        interactions = [
            {
                "request": {"body": {"messages": [{"role": "user", "content": "hi"}]}},
                "response": {"content": "hello"},
            }
        ]
        cassette = LLMCassette(name="test", interactions=interactions)
        assert len(cassette.interactions) == 1
        assert cassette.interactions[0]["response"]["content"] == "hello"


class TestLLMVCR:
    def test_list_cassettes_empty_directory(self, tmp_path: Path) -> None:
        cassettes_dir = tmp_path / "cassettes"
        cassettes_dir.mkdir()
        vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        assert vcr.list_cassettes() == []

    def test_list_cassettes_nonexistent_directory(self) -> None:
        vcr = LLMVCR(cassette_dir="/nonexistent/path/12345")
        assert vcr.list_cassettes() == []

    def test_list_cassettes_with_files(self, tmp_path: Path) -> None:
        cassettes_dir = tmp_path / "cassettes"
        cassettes_dir.mkdir()
        cassette_empty = json.dumps({"version": 1, "interactions": []})
        (cassettes_dir / "scenario_a.json").write_text(cassette_empty)
        (cassettes_dir / "scenario_b.json").write_text(cassette_empty)
        vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        cassettes = vcr.list_cassettes()
        assert cassettes == ["scenario_a", "scenario_b"]

    def test_start_and_stop_recording_creates_file(self, tmp_path: Path) -> None:
        cassettes_dir = tmp_path / "cassettes"
        vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        vcr.start_recording("my_test")
        vcr._recording.record("my_test", {"uri": "/test", "method": "GET"}, {"status": 200})
        vcr.stop_recording()
        cassette_file = cassettes_dir / "my_test.json"
        assert cassette_file.exists()
        data = json.loads(cassette_file.read_text())
        assert len(data["interactions"]) == 1

    def test_replay_loads_cassette(self, tmp_path: Path) -> None:
        cassettes_dir = tmp_path / "cassettes"
        cassettes_dir.mkdir()
        cassette_data = {
            "version": 1,
            "interactions": [
                {
                    "request": {
                        "uri": "llm://gpt-4o/chat",
                        "method": "POST",
                        "body": {
                            "messages": [{"role": "user", "content": "test"}],
                            "model": "gpt-4o",
                        },
                    },
                    "response": {"content": "response"},
                }
            ],
        }
        (cassettes_dir / "scenario_a.json").write_text(json.dumps(cassette_data))
        vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        cassette = vcr.replay("scenario_a")
        assert cassette.name == "scenario_a"
        assert len(cassette.interactions) == 1
        assert cassette.interactions[0]["response"]["content"] == "response"

    def test_replay_missing_cassette_raises(self, tmp_path: Path) -> None:
        cassettes_dir = tmp_path / "cassettes"
        cassettes_dir.mkdir()
        vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        with pytest.raises(FileNotFoundError, match="Cassette not found"):
            vcr.replay("nonexistent")

    def test_verify_trajectory_exact_match(self) -> None:
        interactions = [
            {
                "request": {"body": {"messages": [{"role": "user", "content": "hello"}]}},
                "response": {},
            },
            {
                "request": {"body": {"messages": [{"role": "user", "content": "world"}]}},
                "response": {},
            },
        ]
        cassette = LLMCassette(name="test", interactions=interactions)
        vcr = LLMVCR()
        actual = [
            {"messages": [{"role": "user", "content": "hello"}]},
            {"messages": [{"role": "user", "content": "world"}]},
        ]
        result = vcr.verify_trajectory(cassette, actual)
        assert result["passed"] is True
        assert result["matched"] == 2
        assert result["total_expected"] == 2
        assert result["total_actual"] == 2

    def test_verify_trajectory_mismatch(self) -> None:
        interactions = [
            {
                "request": {"body": {"messages": [{"role": "user", "content": "hello"}]}},
                "response": {},
            },
        ]
        cassette = LLMCassette(name="test", interactions=interactions)
        vcr = LLMVCR()
        actual = [
            {"messages": [{"role": "user", "content": "goodbye"}]},
        ]
        result = vcr.verify_trajectory(cassette, actual)
        assert result["passed"] is False
        assert result["matched"] == 0
        assert len(result["mismatches"]) == 1

    def test_verify_trajectory_length_mismatch_shorter(self) -> None:
        interactions = [
            {"request": {"body": {"messages": [{"role": "user", "content": "a"}]}}, "response": {}},
            {"request": {"body": {"messages": [{"role": "user", "content": "b"}]}}, "response": {}},
        ]
        cassette = LLMCassette(name="test", interactions=interactions)
        vcr = LLMVCR()
        actual = [{"messages": [{"role": "user", "content": "a"}]}]
        result = vcr.verify_trajectory(cassette, actual)
        assert result["passed"] is False
        assert result["mismatches"] == [
            {"index": 1, "expected": [{"role": "user", "content": "b"}], "actual": None}
        ]

    def test_verify_trajectory_length_mismatch_longer(self) -> None:
        interactions = [
            {"request": {"body": {"messages": [{"role": "user", "content": "a"}]}}, "response": {}},
        ]
        cassette = LLMCassette(name="test", interactions=interactions)
        vcr = LLMVCR()
        actual = [
            {"messages": [{"role": "user", "content": "a"}]},
            {"messages": [{"role": "user", "content": "extra"}]},
        ]
        result = vcr.verify_trajectory(cassette, actual)
        assert result["passed"] is False
        assert result["mismatches"][0]["actual"] == [{"role": "user", "content": "extra"}]


class TestNodeTiming:
    def test_node_timing_defaults(self) -> None:
        nt = NodeTiming(node_name="agent", start_time=100.0)
        assert nt.node_name == "agent"
        assert nt.start_time == 100.0
        assert nt.end_time is None
        assert nt.duration_ms is None
        assert nt.llm_calls == 0
        assert nt.tool_calls == 0
        assert nt.retry_count == 0

    def test_node_timing_duration(self) -> None:
        nt = NodeTiming(
            node_name="agent",
            start_time=100.0,
            end_time=100.5,
            duration_ms=500.0,
            llm_calls=3,
            tool_calls=1,
        )
        assert nt.duration_ms == 500.0
        assert nt.llm_calls == 3
        assert nt.tool_calls == 1


class TestTimingCollector:
    def test_empty_collector_metrics(self) -> None:
        collector = TimingCollector()
        assert collector.to_metrics() == {}
        tm = collector.to_trajectory_metrics()
        assert tm["slow_nodes"] == []
        assert tm["bottleneck"] is None

    def test_start_end_node_computes_duration(self) -> None:
        collector = TimingCollector()
        collector.start_node("agent")
        time.sleep(0.05)
        collector.end_node("agent")
        metrics = collector.to_metrics()
        assert metrics["node_count"] == 1
        assert metrics["total_duration_ms"] > 0
        per_node = metrics["per_node"]["agent"]
        assert per_node["count"] == 1
        assert per_node["avg_ms"] > 0

    def test_multiple_nodes_accumulate_separately(self) -> None:
        collector = TimingCollector()
        collector.start_node("node_a")
        time.sleep(0.02)
        collector.end_node("node_a", llm_calls=1)
        collector.start_node("node_b")
        time.sleep(0.02)
        collector.end_node("node_b", tool_calls=2)
        metrics = collector.to_metrics()
        assert metrics["node_count"] == 2
        assert metrics["total_llm_calls"] == 1
        assert metrics["total_tool_calls"] == 2
        assert "node_a" in metrics["per_node"]
        assert "node_b" in metrics["per_node"]

    def test_same_node_multiple_times_averages(self) -> None:
        collector = TimingCollector()
        collector.start_node("agent")
        time.sleep(0.02)
        collector.end_node("agent")
        collector.start_node("agent")
        time.sleep(0.04)
        collector.end_node("agent")
        metrics = collector.to_metrics()
        agent = metrics["per_node"]["agent"]
        assert agent["count"] == 2
        assert agent["avg_ms"] > 0

    def test_to_trajectory_metrics_bottleneck(self) -> None:
        collector = TimingCollector()
        collector.start_node("fast")
        time.sleep(0.01)
        collector.end_node("fast")
        collector.start_node("slow")
        time.sleep(0.05)
        collector.end_node("slow")
        traj = collector.to_trajectory_metrics()
        assert traj["bottleneck"] == "slow"
        assert len(traj["slow_nodes"]) == 2

    def test_reset_clears_all_timings(self) -> None:
        collector = TimingCollector()
        collector.start_node("agent")
        time.sleep(0.02)
        collector.end_node("agent")
        collector.reset()
        assert collector.to_metrics() == {}
        tm = collector.to_trajectory_metrics()
        assert tm["slow_nodes"] == []
        assert tm["bottleneck"] is None


class TestDeepEvalIntegration:
    def test_disabled_by_default(self) -> None:
        integration = DeepEvalIntegration()
        assert integration._enabled is False

    def test_score_before_enable_returns_fallback(self) -> None:
        integration = DeepEvalIntegration()
        result = integration.score_trajectory([], {})
        assert result["engine"] == "evalforge"
        assert result["score"] is None
        assert "DeepEval not enabled" in result["error"]

    def test_enable_without_deepeval_installed(self) -> None:
        integration = DeepEvalIntegration()
        with pytest.raises(ImportError, match="DeepEval is not installed"):
            integration.enable()

    def test_callback_does_nothing_when_disabled(self) -> None:
        integration = DeepEvalIntegration()
        callback = integration.to_runtime_callback()
        callback({})  # No error expected

    def test_score_falls_back_gracefully_on_error(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True
        result = integration.score_trajectory([], {"input": "test"})
        assert result["engine"] == "deepeval"
        assert result["score"] is None
        assert result["error"] is not None


class TestFullVCRPipeline:
    def test_record_replay_verify_cycle(self, tmp_path: Path) -> None:
        cassettes_dir = tmp_path / "cassettes"
        vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        vcr.start_recording("integration_test")
        vcr._recording.record(
            "integration_test",
            {
                "uri": "llm://gpt-4o/chat",
                "method": "POST",
                "body": {
                    "messages": [{"role": "user", "content": "compute 2+2"}],
                    "model": "gpt-4o",
                },
            },
            {"content": "The answer is 4."},
        )
        vcr._recording.record(
            "integration_test",
            {
                "uri": "llm://gpt-4o/chat",
                "method": "POST",
                "body": {
                    "messages": [{"role": "user", "content": "explain your reasoning"}],
                    "model": "gpt-4o",
                },
            },
            {"content": "2 + 2 = 4 because addition is commutative."},
        )
        vcr.stop_recording()
        assert (cassettes_dir / "integration_test.json").exists()
        replay_vcr = LLMVCR(cassette_dir=str(cassettes_dir))
        cassette = replay_vcr.replay("integration_test")
        actual_trajectory = [
            {"messages": [{"role": "user", "content": "compute 2+2"}]},
            {"messages": [{"role": "user", "content": "explain your reasoning"}]},
        ]
        result = replay_vcr.verify_trajectory(cassette, actual_trajectory)
        assert result["passed"] is True
        assert result["matched"] == 2
