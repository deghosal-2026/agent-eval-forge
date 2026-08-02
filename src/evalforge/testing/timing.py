"""Node-level timing collection for LangGraph runs.

Captures per-node timing, LLM call counts, tool call counts, and retry
information. Produces aggregate metrics for trajectory artifact enrichment.
"""

from __future__ import annotations

import statistics
import time as time_mod
from dataclasses import dataclass
from typing import Any


@dataclass
class NodeTiming:
    """Timing data for a single node execution.

    Attributes:
        node_name: Name of the node.
        start_time: Unix timestamp when the node started.
        end_time: Unix timestamp when the node ended (None if still running).
        duration_ms: Wall-clock duration in milliseconds (None if not yet ended).
        llm_calls: Number of LLM invocations during this node.
        tool_calls: Number of tool invocations during this node.
        retry_count: Number of retries observed.
    """
    node_name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    llm_calls: int = 0
    tool_calls: int = 0
    retry_count: int = 0


class TimingCollector:
    """Collects per-node timing data and produces aggregate metrics.

    Typical usage::

        collector = TimingCollector()
        collector.start_node("planner")
        # ... run node ...
        collector.end_node("planner", llm_calls=2)
        metrics = collector.to_metrics()
    """

    def __init__(self) -> None:
        self._timings: list[NodeTiming] = []
        self._current_node: str | None = None
        self._node_start_times: dict[str, float] = {}

    def start_node(self, name: str) -> None:
        """Begin timing for *name*.

        If a node with the same name has already been started, its previous
        start time is overwritten.

        Args:
            name: Node identifier.
        """
        now = time_mod.time()
        self._current_node = name
        self._node_start_times[name] = now

    def end_node(
        self, name: str, llm_calls: int = 0, tool_calls: int = 0, retry_count: int = 0
    ) -> None:
        """Finalise timing for *name* and append a NodeTiming record.

        Args:
            name: Node identifier (must match a previous ``start_node`` call).
            llm_calls: LLM invocations to attribute to this node.
            tool_calls: Tool invocations to attribute.
            retry_count: Retries observed.
        """
        now = time_mod.time()
        start = self._node_start_times.pop(name, now)
        duration_ms = round((now - start) * 1000, 2)
        timing = NodeTiming(
            node_name=name,
            start_time=start,
            end_time=now,
            duration_ms=duration_ms,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            retry_count=retry_count,
        )
        self._timings.append(timing)
        if self._current_node == name:
            self._current_node = None

    def to_metrics(self) -> dict[str, Any]:
        """Aggregate all collected timings into a summary dict.

        Returns:
            Dict with keys ``total_duration_ms``, ``total_llm_calls``,
            ``total_tool_calls``, ``total_retries``, ``node_count``,
            and ``per_node`` breakdown.
        """
        if not self._timings:
            return {}
        per_node: dict[str, list[float]] = {}
        for t in self._timings:
            if t.duration_ms is not None:
                per_node.setdefault(t.node_name, []).append(t.duration_ms)
        metrics: dict[str, Any] = {
            "total_duration_ms": round(sum(t.duration_ms or 0 for t in self._timings), 2),
            "total_llm_calls": sum(t.llm_calls for t in self._timings),
            "total_tool_calls": sum(t.tool_calls for t in self._timings),
            "total_retries": sum(t.retry_count for t in self._timings),
            "node_count": len(self._timings),
            "per_node": {},
        }
        for node, durations in per_node.items():
            metrics["per_node"][node] = {
                "count": len(durations),
                "avg_ms": round(statistics.mean(durations), 2),
                "max_ms": round(max(durations), 2),
                "min_ms": round(min(durations), 2),
                "total_ms": round(sum(durations), 2),
            }
        return metrics

    def to_trajectory_metrics(self) -> dict[str, Any]:
        """Like ``to_metrics`` but also identifies slow nodes and bottlenecks.

        Returns:
            Dict with additional keys ``slow_nodes`` (sorted by avg_ms
            descending) and ``bottleneck`` (the single slowest node name).
        """
        base = self.to_metrics()
        if not base:
            base["slow_nodes"] = []
            base["bottleneck"] = None
            return base
        per_node = base.get("per_node", {})
        slow_nodes = sorted(
            per_node.items(),
            key=lambda kv: kv[1].get("avg_ms", 0),
            reverse=True,
        )
        base["slow_nodes"] = [
            {"node": name, "avg_ms": data["avg_ms"]} for name, data in slow_nodes
        ]
        base["bottleneck"] = slow_nodes[0][0] if slow_nodes else None
        return base

    def reset(self) -> None:
        """Clear all collected timings and reset the collector to initial state."""
        self._timings.clear()
        self._current_node = None
        self._node_start_times.clear()
