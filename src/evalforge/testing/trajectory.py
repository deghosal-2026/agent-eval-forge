"""Trajectory metrics — extracts enriched metrics from agent trajectories.

Expands trajectory-level data into structured metrics: node-level timing,
tool call duration, and retry counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evalforge.models.artifact import RunArtifact, TrajectoryStep


@dataclass
class ToolCallTiming:
    """Timing and metadata for a single tool call in a trajectory.

    Attributes:
        tool: Name of the tool invoked.
        call_index: Zero-based index among all tool calls.
        duration_ms: Wall-clock duration of the call, if known.
        args: Arguments passed to the tool.
        result_size: Character count of the stringified result.
        error: Error message if the call failed.
    """
    tool: str
    call_index: int
    duration_ms: int | None = None
    args: dict[str, Any] | None = None
    result_size: int | None = None
    error: str | None = None


@dataclass
class RetryPattern:
    """A detected retry pattern — consecutive calls to the same tool.

    Attributes:
        tool: Tool that was retried.
        attempts: Number of consecutive calls.
        consecutive: Whether calls were truly consecutive (always True currently).
        args_changed: Whether arguments differed between the first and last call.
    """
    tool: str
    attempts: int
    consecutive: bool
    args_changed: bool


@dataclass
class TrajectoryMetrics:
    """Aggregate metrics derived by analyzing a full trajectory.

    Attributes:
        total_steps: Number of steps in the trajectory.
        tool_calls: Count of steps with type ``tool_call``.
        tool_results: Count of steps with type ``tool_result``.
        responses: Count of steps with type ``response``.
        notes: Count of steps with type ``note``.
        errors: Count of steps that contain an error.
        total_duration_ms: Summed duration across all steps.
        avg_tool_duration_ms: Mean tool-call duration.
        max_tool_duration_ms: Maximum tool-call duration.
        min_tool_duration_ms: Minimum tool-call duration.
        tool_timings: Per-call tool timing breakdowns.
        retry_patterns: Detected retry patterns.
        unique_tools: Distinct tool names used.
        tool_call_ratio: Fraction of steps that are tool calls.
        error_rate: Fraction of steps with errors.
        steps_per_second: Overall throughput in steps per second.
    """
    total_steps: int = 0
    tool_calls: int = 0
    tool_results: int = 0
    responses: int = 0
    notes: int = 0
    errors: int = 0
    total_duration_ms: int = 0
    avg_tool_duration_ms: float = 0.0
    max_tool_duration_ms: int = 0
    min_tool_duration_ms: int = 0
    tool_timings: list[ToolCallTiming] = field(default_factory=list)
    retry_patterns: list[RetryPattern] = field(default_factory=list)
    unique_tools: list[str] = field(default_factory=list)
    tool_call_ratio: float = 0.0
    error_rate: float = 0.0
    steps_per_second: float = 0.0


class TrajectoryAnalyzer:
    """Analyzes trajectories and extracts enriched metrics."""

    @staticmethod
    def analyze(artifact: RunArtifact) -> TrajectoryMetrics:
        """Extract trajectory metrics from a run artifact.

        Classifies each step by type, aggregates durations, detects retry
        patterns, and computes derived metrics such as throughput and error rate.

        Args:
            artifact: A completed ``RunArtifact`` with a populated ``trajectory``.

        Returns:
            A :class:`TrajectoryMetrics` instance.
        """
        steps = artifact.trajectory
        metrics = TrajectoryMetrics(total_steps=len(steps))
        if not steps:
            return metrics

        tool_call_steps: list[TrajectoryStep] = []
        tool_result_steps: list[TrajectoryStep] = []
        durations: list[int] = []
        tool_names: list[str] = []

        for step in steps:
            if step.type == "tool_call":
                metrics.tool_calls += 1
                tool_call_steps.append(step)
                if step.tool:
                    tool_names.append(step.tool)
                if step.duration_ms is not None:
                    durations.append(step.duration_ms)
            elif step.type == "tool_result":
                metrics.tool_results += 1
                tool_result_steps.append(step)
            elif step.type == "response":
                metrics.responses += 1
            elif step.type == "note":
                metrics.notes += 1
            if step.error:
                metrics.errors += 1
            if step.duration_ms is not None:
                metrics.total_duration_ms += step.duration_ms

        metrics.unique_tools = list(dict.fromkeys(tool_names))
        metrics.tool_call_ratio = (
            metrics.tool_calls / metrics.total_steps if metrics.total_steps else 0.0
        )
        metrics.error_rate = metrics.errors / metrics.total_steps if metrics.total_steps else 0.0

        if durations:
            metrics.avg_tool_duration_ms = sum(durations) / len(durations)
            metrics.max_tool_duration_ms = max(durations)
            metrics.min_tool_duration_ms = min(durations)

        if artifact.timestamp.duration_ms > 0:
            metrics.steps_per_second = (
                metrics.total_steps / (artifact.timestamp.duration_ms / 1000.0)
            )

        metrics.tool_timings = TrajectoryAnalyzer._extract_tool_timings(
            tool_call_steps, tool_result_steps
        )
        metrics.retry_patterns = TrajectoryAnalyzer._detect_retries(tool_call_steps)
        return metrics

    @staticmethod
    def _extract_tool_timings(
        call_steps: list[TrajectoryStep], result_steps: list[TrajectoryStep]
    ) -> list[ToolCallTiming]:
        """Build :class:`ToolCallTiming` entries by pairing call and result steps.

        Args:
            call_steps: Trajectory steps of type ``tool_call``.
            result_steps: Trajectory steps of type ``tool_result``, expected
                to be in the same order as calls.

        Returns:
            List of ``ToolCallTiming``, one per tool call.
        """
        timings: list[ToolCallTiming] = []
        for i, call in enumerate(call_steps):
            result_size = None
            error = None
            if i < len(result_steps):
                result = result_steps[i]
                if result.result is not None:
                    result_size = len(str(result.result))
                if result.error:
                    error = result.error
            timings.append(
                ToolCallTiming(
                    tool=call.tool or "",
                    call_index=i,
                    duration_ms=call.duration_ms,
                    args=call.args,
                    result_size=result_size,
                    error=error,
                )
            )
        return timings

    @staticmethod
    def _detect_retries(call_steps: list[TrajectoryStep]) -> list[RetryPattern]:
        """Scan tool call steps for consecutive same-tool retries.

        A retry pattern is recorded when the same tool is called two or more
        times consecutively.

        Args:
            call_steps: Trajectory steps of type ``tool_call``.

        Returns:
            List of :class:`RetryPattern` entries.
        """
        patterns: list[RetryPattern] = []
        if len(call_steps) < 2:
            return patterns

        i = 0
        while i < len(call_steps):
            tool = call_steps[i].tool or ""
            count = 1
            consecutive = True
            args_changed = False
            while i + count < len(call_steps):
                next_tool = call_steps[i + count].tool or ""
                if next_tool != tool:
                    break
                if call_steps[i + count].args != call_steps[i].args:
                    args_changed = True
                count += 1
            if count > 1:
                patterns.append(
                    RetryPattern(
                        tool=tool,
                        attempts=count,
                        consecutive=consecutive,
                        args_changed=args_changed,
                    )
                )
            i += count
        return patterns

    @staticmethod
    def to_dict(artifact: RunArtifact) -> dict[str, Any]:
        """Analyze a run artifact and return metrics as a plain dict.

        Convenience method that calls :meth:`analyze` and serialises the
        result into a JSON-safe dict.

        Args:
            artifact: A completed ``RunArtifact``.

        Returns:
            Dict with all ``TrajectoryMetrics`` fields as flat values, plus
            ``retry_patterns`` and ``tool_timings`` as lists of dicts.
        """
        m = TrajectoryAnalyzer.analyze(artifact)
        return {
            "total_steps": m.total_steps,
            "tool_calls": m.tool_calls,
            "tool_results": m.tool_results,
            "responses": m.responses,
            "errors": m.errors,
            "total_duration_ms": m.total_duration_ms,
            "avg_tool_duration_ms": round(m.avg_tool_duration_ms, 2),
            "max_tool_duration_ms": m.max_tool_duration_ms,
            "min_tool_duration_ms": m.min_tool_duration_ms,
            "unique_tools": m.unique_tools,
            "tool_call_ratio": round(m.tool_call_ratio, 4),
            "error_rate": round(m.error_rate, 4),
            "steps_per_second": round(m.steps_per_second, 2),
            "retry_count": len(m.retry_patterns),
            "retry_patterns": [
                {
                    "tool": p.tool,
                    "attempts": p.attempts,
                    "consecutive": p.consecutive,
                    "args_changed": p.args_changed,
                }
                for p in m.retry_patterns
            ],
            "tool_timings": [
                {
                    "tool": t.tool,
                    "call_index": t.call_index,
                    "duration_ms": t.duration_ms,
                    "result_size": t.result_size,
                    "error": t.error,
                }
                for t in m.tool_timings
            ],
        }
