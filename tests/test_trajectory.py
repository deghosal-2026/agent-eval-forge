from __future__ import annotations

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps, TrajectoryStep
from evalforge.testing.trajectory import TrajectoryAnalyzer


def _make_artifact(steps: list[TrajectoryStep], duration_ms: int = 1000) -> RunArtifact:
    return RunArtifact(
        id="run-test",
        scenario_id="test-01",
        agent={},
        timestamp=RunTimestamps(start="2024-01-01T00:00:00Z", end="2024-01-01T00:00:01Z",
                                duration_ms=duration_ms),
        output=RunOutput(final="done"),
        trajectory=steps,
        cost=Cost(),
    )


class TestTrajectoryAnalyzer:
    def test_empty_trajectory(self) -> None:
        m = TrajectoryAnalyzer.analyze(_make_artifact([]))
        assert m.total_steps == 0
        assert m.tool_calls == 0

    def test_counts_tool_calls_and_results(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="search", duration_ms=100),
            TrajectoryStep(type="tool_result", tool="search", result={"data": "x"}),
            TrajectoryStep(type="response", content="answer"),
        ]
        m = TrajectoryAnalyzer.analyze(_make_artifact(steps))
        assert m.tool_calls == 1
        assert m.tool_results == 1
        assert m.responses == 1

    def test_duration_stats(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="a", duration_ms=50),
            TrajectoryStep(type="tool_call", tool="b", duration_ms=200),
        ]
        m = TrajectoryAnalyzer.analyze(_make_artifact(steps))
        assert m.avg_tool_duration_ms == 125.0
        assert m.max_tool_duration_ms == 200
        assert m.min_tool_duration_ms == 50

    def test_retry_detection(self) -> None:
        steps = [
            TrajectoryStep(type="tool_call", tool="search", args={"q": "test"}),
            TrajectoryStep(type="tool_call", tool="search", args={"q": "test"}),
            TrajectoryStep(type="tool_call", tool="fetch"),
        ]
        m = TrajectoryAnalyzer.analyze(_make_artifact(steps))
        assert len(m.retry_patterns) == 1
        assert m.retry_patterns[0].tool == "search"
        assert m.retry_patterns[0].attempts == 2

    def test_to_dict_serializable(self) -> None:
        steps = [TrajectoryStep(type="tool_call", tool="x", duration_ms=10)]
        art = _make_artifact(steps)
        d = TrajectoryAnalyzer.to_dict(art)
        assert d["total_steps"] == 1
        assert d["tool_calls"] == 1
        assert isinstance(d["retry_patterns"], list)
