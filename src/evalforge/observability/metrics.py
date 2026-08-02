"""Metrics collection for evaluation runs.

Collects per-scenario timing, cost, cache, and safety data and exports
as structured reports (JSON, Prometheus text format).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class EvalMetrics:
    """Aggregate metrics for an evaluation run.

    Attributes:
        total_scenarios: Number of scenarios executed.
        passed: Count of passed scenarios.
        failed: Count of failed scenarios.
        warnings: Count of scenarios with warning status.
        total_duration_ms: Sum of all scenario durations.
        avg_scenario_duration_ms: Mean scenario duration.
        avg_agent_cost_usd: Mean agent LLM cost per scenario.
        avg_judge_cost_usd: Mean judge LLM cost per scenario.
        cache_hit_rate: Fraction of LLM calls served from cache.
        safety_violations: Number of safety violations encountered.
        agents_per_second: Overall throughput (scenarios per second).
    """
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    total_duration_ms: float = 0.0
    avg_scenario_duration_ms: float = 0.0
    avg_agent_cost_usd: float = 0.0
    avg_judge_cost_usd: float = 0.0
    cache_hit_rate: float = 0.0
    safety_violations: int = 0
    agents_per_second: float = 0.0


class MetricsCollector:
    """Collects per-scenario and per-LLM-call metrics during an evaluation run."""

    def __init__(self) -> None:
        self._metrics: list[dict[str, Any]] = []
        self._llm_calls: list[dict[str, Any]] = []
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._safety_violations: list[dict[str, str]] = []
        self._start_time: float | None = None

    def start_run(self) -> None:
        """Record the wall-clock start time of the run."""
        self._start_time = time.time()

    def record_scenario(
        self, scenario_id: str, score: float, duration_ms: float, status: str
    ) -> None:
        """Record a completed scenario's metrics.

        Args:
            scenario_id: Scenario identifier.
            score: Evaluation score.
            duration_ms: Wall-clock duration in milliseconds.
            status: One of ``"passed"``, ``"failed"``, ``"warn"``.
        """
        self._metrics.append(
            {
                "scenario_id": scenario_id,
                "score": score,
                "duration_ms": duration_ms,
                "status": status,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def record_llm_call(
        self, provider: str, model: str, tokens: int, cost_usd: float, duration_ms: float
    ) -> None:
        """Record an LLM API call.

        Args:
            provider: Provider name (e.g. ``"openai"``).
            model: Model identifier (e.g. ``"gpt-4o"``).
            tokens: Token count for the call.
            cost_usd: Cost in USD.
            duration_ms: Latency in milliseconds.
        """
        self._llm_calls.append(
            {
                "provider": provider,
                "model": model,
                "tokens": tokens,
                "cost_usd": cost_usd,
                "duration_ms": duration_ms,
            }
        )

    def record_cache_hit(self) -> None:
        """Increment the cache-hit counter."""
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        """Increment the cache-miss counter."""
        self._cache_misses += 1

    def record_safety_violation(self, scenario_id: str, violation_type: str) -> None:
        """Record a safety violation for a scenario.

        Args:
            scenario_id: Scenario identifier.
            violation_type: Type/category of the violation.
        """
        self._safety_violations.append(
            {"scenario_id": scenario_id, "violation_type": violation_type}
        )

    def collect(self) -> EvalMetrics:
        """Aggregate all collected data into an :class:`EvalMetrics` instance.

        Returns:
            Computed metrics summary.
        """
        total = len(self._metrics)
        passed = sum(1 for m in self._metrics if m["status"] == "passed")
        failed = sum(1 for m in self._metrics if m["status"] == "failed")
        warnings_count = sum(1 for m in self._metrics if m["status"] == "warn")

        total_duration = sum(m["duration_ms"] for m in self._metrics)
        avg_duration = total_duration / total if total > 0 else 0.0

        agent_calls = [
            c for c in self._llm_calls if c.get("role", "agent") == "agent"
        ] or self._llm_calls
        judge_calls = [c for c in self._llm_calls if c.get("role") == "judge"]

        avg_agent_cost = (
            sum(c["cost_usd"] for c in agent_calls) / len(agent_calls)
            if agent_calls
            else 0.0
        )
        avg_judge_cost = (
            sum(c["cost_usd"] for c in judge_calls) / len(judge_calls)
            if judge_calls
            else 0.0
        )

        total_cache = self._cache_hits + self._cache_misses
        cache_rate = self._cache_hits / total_cache if total_cache > 0 else 0.0

        elapsed = time.time() - self._start_time if self._start_time else 0.0
        agents_per_sec = total / elapsed if elapsed > 0 else 0.0

        return EvalMetrics(
            total_scenarios=total,
            passed=passed,
            failed=failed,
            warnings=warnings_count,
            total_duration_ms=total_duration,
            avg_scenario_duration_ms=round(avg_duration, 2),
            avg_agent_cost_usd=round(avg_agent_cost, 6),
            avg_judge_cost_usd=round(avg_judge_cost, 6),
            cache_hit_rate=round(cache_rate, 4),
            safety_violations=len(self._safety_violations),
            agents_per_second=round(agents_per_sec, 2),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return metrics, LLM calls, and safety violations as a dict.

        Returns:
            Dict with keys ``metrics``, ``llm_calls``, ``safety_violations``.
        """
        metrics = self.collect()
        return {
            "metrics": {
                "total_scenarios": metrics.total_scenarios,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "warnings": metrics.warnings,
                "total_duration_ms": metrics.total_duration_ms,
                "avg_scenario_duration_ms": metrics.avg_scenario_duration_ms,
                "avg_agent_cost_usd": metrics.avg_agent_cost_usd,
                "avg_judge_cost_usd": metrics.avg_judge_cost_usd,
                "cache_hit_rate": metrics.cache_hit_rate,
                "safety_violations": metrics.safety_violations,
                "agents_per_second": metrics.agents_per_second,
            },
            "llm_calls": self._llm_calls,
            "safety_violations": self._safety_violations,
        }

    def to_json(self) -> str:
        """Serialize metrics to a JSON string.

        Returns:
            Indented JSON representation of :meth:`to_dict`.
        """
        return json.dumps(self.to_dict(), indent=2)

    def to_prometheus(self) -> str:
        """Render metrics as Prometheus text-format exposition.

        Each metric is emitted as a gauge with a ``# HELP`` and ``# TYPE`` line.
        Safety violations are emitted as counters.

        Returns:
            Prometheus-formatted string.
        """
        metrics = self.collect()
        lines: list[str] = []

        def _safe_name(n: str) -> str:
            return n.replace("-", "_").replace(" ", "_")

        gauges = [
            ("evalforge_scenarios_total", metrics.total_scenarios),
            ("evalforge_scenarios_passed", metrics.passed),
            ("evalforge_scenarios_failed", metrics.failed),
            ("evalforge_scenarios_warnings", metrics.warnings),
            ("evalforge_total_duration_ms", metrics.total_duration_ms),
            ("evalforge_avg_scenario_duration_ms", metrics.avg_scenario_duration_ms),
            ("evalforge_avg_agent_cost_usd", metrics.avg_agent_cost_usd),
            ("evalforge_avg_judge_cost_usd", metrics.avg_judge_cost_usd),
            ("evalforge_cache_hit_rate", metrics.cache_hit_rate),
            ("evalforge_safety_violations", metrics.safety_violations),
            ("evalforge_agents_per_second", metrics.agents_per_second),
        ]

        ts = int(time.time() * 1000)
        for name, value in gauges:
            safe_name = _safe_name(name)
            lines.append(f"# HELP {safe_name} EvalForge evaluation metric")
            lines.append(f"# TYPE {safe_name} gauge")
            lines.append(f"{safe_name} {value} {ts}")

        for violation in self._safety_violations:
            safe_name = _safe_name(f"evalforge_safety_violation_{violation['violation_type']}")
            lines.append(f"# HELP {safe_name} Safety violation count")
            lines.append(f"# TYPE {safe_name} counter")
            lines.append(f"{safe_name} 1 {ts}")

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Clear all collected data and reset the collector."""
        self._metrics.clear()
        self._llm_calls.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._safety_violations.clear()
        self._start_time = None
