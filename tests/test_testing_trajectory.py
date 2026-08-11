# ruff: noqa: S108
"""Tests for evalforge.testing.trajectory."""

import pytest

from evalforge.models.artifact import RunArtifact, RunOutput, RunTimestamps, TrajectoryStep
from evalforge.testing.trajectory import (
    RetryPattern,
    ToolCallTiming,
    TrajectoryAnalyzer,
    TrajectoryMetrics,
)


class TestToolCallTiming:
    def test_defaults(self) -> None:
        t = ToolCallTiming(tool="read", call_index=0)
        assert t.tool == "read"
        assert t.call_index == 0
        assert t.duration_ms is None
        assert t.args is None
        assert t.result_size is None
        assert t.error is None

    def test_full_values(self) -> None:
        t = ToolCallTiming(
            tool="write",
            call_index=3,
            duration_ms=150,
            args={"path": "/tmp/x"},
            result_size=42,
            error="permission denied",
        )
        assert t.tool == "write"
        assert t.call_index == 3
        assert t.duration_ms == 150
        assert t.args == {"path": "/tmp/x"}
        assert t.result_size == 42
        assert t.error == "permission denied"


class TestRetryPattern:
    def test_creation(self) -> None:
        r = RetryPattern(tool="read", attempts=3, consecutive=True, args_changed=False)
        assert r.tool == "read"
        assert r.attempts == 3
        assert r.consecutive is True
        assert r.args_changed is False


class TestTrajectoryMetrics:
    def test_defaults(self) -> None:
        m = TrajectoryMetrics()
        assert m.total_steps == 0
        assert m.tool_calls == 0
        assert m.tool_results == 0
        assert m.responses == 0
        assert m.notes == 0
        assert m.errors == 0
        assert m.total_duration_ms == 0
        assert m.avg_tool_duration_ms == 0.0
        assert m.max_tool_duration_ms == 0
        assert m.min_tool_duration_ms == 0
        assert m.tool_timings == []
        assert m.retry_patterns == []
        assert m.unique_tools == []
        assert m.tool_call_ratio == 0.0
        assert m.error_rate == 0.0
        assert m.steps_per_second == 0.0


def _make_artifact(
    run_id="r1",
    scenario_id="s1",
    trajectory=None,
    start="2025-01-01T00:00:00Z",
    end="2025-01-01T00:01:00Z",
    duration_ms=60000,
    status: str = "completed",
):
    return RunArtifact(
        id=run_id,
        scenario_id=scenario_id,
        timestamp=RunTimestamps(start=start, end=end, duration_ms=duration_ms),
        output=RunOutput(final="some output"),
        trajectory=trajectory or [],
        status=status,  # type: ignore[arg-type]
    )


class TestTrajectoryAnalyzerAnalyze:
    def test_empty_trajectory(self) -> None:
        artifact = _make_artifact(trajectory=[])
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.total_steps == 0
        assert metrics.tool_calls == 0

    def test_tool_call_step(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", args={"path": "/f"})
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.tool_calls == 1
        assert metrics.unique_tools == ["read"]
        assert metrics.tool_call_ratio == 1.0

    def test_tool_result_step(self) -> None:
        steps = [
            TrajectoryStep(type="tool_result", tool="read", result="content")
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.tool_results == 1
        assert metrics.tool_calls == 0

    def test_response_step(self) -> None:
        steps = [
            TrajectoryStep(type="response", content="hello")
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.responses == 1
        assert metrics.tool_calls == 0

    def test_note_step(self) -> None:
        steps = [
            TrajectoryStep(type="note", content="thinking...")
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.notes == 1

    def test_error_step(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", error="failed")
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.errors == 1
        assert metrics.error_rate == 1.0

    def test_mixed_steps(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", duration_ms=100),
            TrajectoryStep(type="tool_result", tool="read"),
            TrajectoryStep(type="response", content="done"),
            TrajectoryStep(type="note", content="note"),
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.total_steps == 4
        assert metrics.tool_calls == 1
        assert metrics.tool_results == 1
        assert metrics.responses == 1
        assert metrics.notes == 1
        assert metrics.tool_call_ratio == 0.25

    def test_tool_durations_computed(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", duration_ms=100),
            TrajectoryStep(type="tool_call", tool="write", duration_ms=300),
            TrajectoryStep(type="tool_call", tool="read", duration_ms=200),
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.avg_tool_duration_ms == 200.0
        assert metrics.max_tool_duration_ms == 300
        assert metrics.min_tool_duration_ms == 100
        assert metrics.total_duration_ms == 600

    def test_no_tool_durations(self) -> None:
        steps = [
            TrajectoryStep(type="response", content="ok"),
            TrajectoryStep(type="note", content="thinking"),
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.avg_tool_duration_ms == 0.0
        assert metrics.max_tool_duration_ms == 0
        assert metrics.min_tool_duration_ms == 0

    def test_total_duration_includes_all_steps(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", duration_ms=50),
            TrajectoryStep(type="tool_result", tool="read", duration_ms=50),
            TrajectoryStep(type="response", duration_ms=100),
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.total_duration_ms == 200

    def test_steps_per_second(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read"),
            TrajectoryStep(type="response"),
        ]
        artifact = _make_artifact(duration_ms=2000, trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.steps_per_second == 1.0

    def test_steps_per_second_zero_duration(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read"),
        ]
        artifact = _make_artifact(duration_ms=0, trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.steps_per_second == 0.0

    def test_unique_tools_preserves_order(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="b"),
            TrajectoryStep(type="tool_call", tool="a"),
            TrajectoryStep(type="tool_call", tool="c"),
            TrajectoryStep(type="tool_call", tool="a"),
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.unique_tools == ["b", "a", "c"]

    def test_tool_with_none_name_handled(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool=None),
        ]
        artifact = _make_artifact(trajectory=steps)
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.tool_calls == 1
        assert metrics.tool_timings[0].tool == ""

    def test_error_rate_no_steps(self) -> None:
        artifact = _make_artifact(trajectory=[])
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.error_rate == 0.0

    def test_tool_call_ratio_no_steps(self) -> None:
        artifact = _make_artifact(trajectory=[])
        metrics = TrajectoryAnalyzer.analyze(artifact)
        assert metrics.tool_call_ratio == 0.0


class TestExtractToolTimings:
    def test_pairs_call_with_result(self) -> None:
        call_steps = [
            TrajectoryStep(type="tool_call", tool="read", duration_ms=100, args={"f": "/x"}),
        ]
        result_steps = [
            TrajectoryStep(type="tool_result", tool="read", result="file contents"),
        ]
        timings = TrajectoryAnalyzer._extract_tool_timings(call_steps, result_steps)
        assert len(timings) == 1
        assert timings[0].tool == "read"
        assert timings[0].call_index == 0
        assert timings[0].duration_ms == 100
        assert timings[0].args == {"f": "/x"}
        assert timings[0].result_size == 13

    def test_fewer_results_than_calls(self) -> None:
        call_steps = [
            TrajectoryStep(type="tool_call", tool="a"),
            TrajectoryStep(type="tool_call", tool="b"),
        ]
        result_steps = [
            TrajectoryStep(type="tool_result", tool="a", result="ok"),
        ]
        timings = TrajectoryAnalyzer._extract_tool_timings(call_steps, result_steps)
        assert len(timings) == 2
        assert timings[1].result_size is None
        assert timings[1].error is None

    def test_result_with_error(self) -> None:
        call_steps = [
            TrajectoryStep(type="tool_call", tool="bad", duration_ms=50),
        ]
        result_steps = [
            TrajectoryStep(type="tool_result", tool="bad", error="timeout"),
        ]
        timings = TrajectoryAnalyzer._extract_tool_timings(call_steps, result_steps)
        assert timings[0].error == "timeout"

    def test_result_none_handled(self) -> None:
        call_steps = [
            TrajectoryStep(type="tool_call", tool="read"),
        ]
        result_steps = [
            TrajectoryStep(type="tool_result", tool="read", result=None),
        ]
        timings = TrajectoryAnalyzer._extract_tool_timings(call_steps, result_steps)
        assert timings[0].result_size is None

    def test_empty_calls(self) -> None:
        timings = TrajectoryAnalyzer._extract_tool_timings([], [])
        assert timings == []


class TestDetectRetries:
    def test_no_retries_single_call(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read"),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert patterns == []

    def test_no_retries_different_tools(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read"),
            TrajectoryStep(type="tool_call", tool="write"),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert patterns == []

    def test_detects_consecutive_same_tool(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", args={"a": 1}),
            TrajectoryStep(type="tool_call", tool="read", args={"a": 1}),
            TrajectoryStep(type="tool_call", tool="read", args={"a": 2}),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert len(patterns) == 1
        assert patterns[0].tool == "read"
        assert patterns[0].attempts == 3
        assert patterns[0].consecutive is True
        assert patterns[0].args_changed is True

    def test_detects_multiple_retry_groups(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read"),
            TrajectoryStep(type="tool_call", tool="read"),
            TrajectoryStep(type="tool_call", tool="write"),
            TrajectoryStep(type="tool_call", tool="write"),
            TrajectoryStep(type="tool_call", tool="write"),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert len(patterns) == 2
        assert patterns[0].tool == "read"
        assert patterns[0].attempts == 2
        assert patterns[1].tool == "write"
        assert patterns[1].attempts == 3

    def test_args_changed_false_when_identical(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", args={"x": 1}),
            TrajectoryStep(type="tool_call", tool="read", args={"x": 1}),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert patterns[0].args_changed is False

    def test_none_tool_handled(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool=None),
            TrajectoryStep(type="tool_call", tool=None),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert len(patterns) == 1
        assert patterns[0].tool == ""
        assert patterns[0].attempts == 2

    def test_empty_steps(self) -> None:
        patterns = TrajectoryAnalyzer._detect_retries([])
        assert patterns == []

    def test_interleaved_tools_no_retry(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read"),
            TrajectoryStep(type="tool_call", tool="write"),
            TrajectoryStep(type="tool_call", tool="read"),
        ]
        patterns = TrajectoryAnalyzer._detect_retries(steps)
        assert len(patterns) == 0


class TestToDict:
    def test_empty_artifact(self) -> None:
        artifact = _make_artifact(trajectory=[])
        d = TrajectoryAnalyzer.to_dict(artifact)
        assert d["total_steps"] == 0
        assert d["tool_calls"] == 0
        assert d["retry_count"] == 0

    def test_with_tool_calls(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", duration_ms=100, args={"f": "/x"}),
            TrajectoryStep(type="tool_result", tool="read", result="data"),
            TrajectoryStep(type="response", content="done"),
        ]
        artifact = _make_artifact(trajectory=steps, duration_ms=3000)
        d = TrajectoryAnalyzer.to_dict(artifact)
        assert d["total_steps"] == 3
        assert d["tool_calls"] == 1
        assert d["tool_results"] == 1
        assert d["responses"] == 1
        assert d["unique_tools"] == ["read"]
        assert d["steps_per_second"] == 1.0
        assert len(d["tool_timings"]) == 1
        assert d["tool_timings"][0]["tool"] == "read"
        assert d["tool_timings"][0]["duration_ms"] == 100
        assert d["tool_timings"][0]["call_index"] == 0

    def test_with_retries(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="read", args={"a": 1}),
            TrajectoryStep(type="tool_call", tool="read", args={"a": 2}),
            TrajectoryStep(type="response"),
        ]
        artifact = _make_artifact(trajectory=steps, duration_ms=1000)
        d = TrajectoryAnalyzer.to_dict(artifact)
        assert d["retry_count"] == 1
        assert len(d["retry_patterns"]) == 1
        assert d["retry_patterns"][0]["tool"] == "read"
        assert d["retry_patterns"][0]["attempts"] == 2
        assert d["retry_patterns"][0]["args_changed"] is True

    def test_error_handling(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="bad", duration_ms=10),
            TrajectoryStep(type="tool_result", tool="bad", error="fail"),
            TrajectoryStep(type="tool_call", tool="read", error="oops"),
        ]
        artifact = _make_artifact(trajectory=steps)
        d = TrajectoryAnalyzer.to_dict(artifact)
        assert d["errors"] == 2
        assert d["error_rate"] == pytest.approx(2 / 3, rel=0.01)
