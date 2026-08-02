"""Tests for observability module — metrics collection and tracing."""

import json

from evalforge.observability.metrics import EvalMetrics, MetricsCollector
from evalforge.observability.tracing import OpenTelemetryTracer


class TestMetricsCollector:
    def test_records_and_collects_metrics(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 0.9, 150.0, "passed")
        collector.record_scenario("sc-2", 0.4, 300.0, "failed")
        collector.record_scenario("sc-3", 0.7, 200.0, "warn")

        metrics = collector.collect()
        assert metrics.total_scenarios == 3
        assert metrics.passed == 1
        assert metrics.failed == 1
        assert metrics.warnings == 1
        assert metrics.total_duration_ms == 650.0

    def test_empty_run_returns_zeros(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        metrics = collector.collect()
        assert metrics.total_scenarios == 0
        assert metrics.passed == 0
        assert metrics.failed == 0
        assert metrics.avg_scenario_duration_ms == 0.0
        assert metrics.agents_per_second == 0.0

    def test_reset_clears_all_metrics(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 1.0, 100.0, "passed")
        collector.record_cache_hit()
        collector.record_safety_violation("sc-1", "disallowed_tool")
        collector.record_llm_call("openai", "gpt-4o", 500, 0.005, 200.0)

        collector.reset()
        metrics = collector.collect()
        assert metrics.total_scenarios == 0
        assert metrics.cache_hit_rate == 0.0
        assert metrics.safety_violations == 0
        assert collector._start_time is None

    def test_multiple_runs_produce_separate_sets(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 1.0, 100.0, "passed")
        collector.record_scenario("sc-2", 1.0, 100.0, "passed")
        first = collector.collect()
        assert first.total_scenarios == 2

        collector.reset()
        collector.start_run()
        collector.record_scenario("sc-3", 0.5, 200.0, "failed")
        second = collector.collect()
        assert second.total_scenarios == 1
        assert second.failed == 1

    def test_llm_cost_averages(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 1.0, 100.0, "passed")
        collector.record_llm_call("openai", "gpt-4o", 500, 0.010, 200.0)
        collector.record_llm_call("openai", "gpt-4o", 300, 0.006, 150.0)
        collector.record_llm_call("anthropic", "claude-3", 400, 0.008, 180.0)

        metrics = collector.collect()
        assert metrics.avg_agent_cost_usd == 0.008

    def test_cache_hit_rate_computation(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 1.0, 100.0, "passed")
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()

        metrics = collector.collect()
        assert metrics.cache_hit_rate > 0.66
        assert metrics.cache_hit_rate < 0.67

    def test_prometheus_format_is_valid(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 1.0, 100.0, "passed")
        collector.record_safety_violation("sc-2", "disallowed_tool")

        output = collector.to_prometheus()
        lines = output.strip().split("\n")
        assert len(lines) > 0
        assert any("evalforge_scenarios_total" in line for line in lines)
        assert any("# HELP" in line for line in lines)
        assert any("# TYPE" in line for line in lines)

    def test_to_dict_and_to_json(self) -> None:
        collector = MetricsCollector()
        collector.start_run()
        collector.record_scenario("sc-1", 1.0, 100.0, "passed")

        d = collector.to_dict()
        assert "metrics" in d
        assert d["metrics"]["total_scenarios"] == 1
        assert d["metrics"]["passed"] == 1
        assert d["metrics"]["avg_scenario_duration_ms"] == 100.0
        assert d["metrics"]["safety_violations"] == 0

        j = collector.to_json()
        parsed = json.loads(j)
        assert parsed["metrics"]["total_scenarios"] == 1
        assert parsed["metrics"]["passed"] == 1

    def test_eval_metrics_defaults(self) -> None:
        m = EvalMetrics()
        assert m.total_scenarios == 0
        assert m.passed == 0
        assert m.failed == 0
        assert m.warnings == 0

    def test_safety_violations_tracked(self) -> None:
        collector = MetricsCollector()
        collector.record_safety_violation("sc-1", "disallowed_tool")
        collector.record_safety_violation("sc-2", "prompt_injection")
        metrics = collector.collect()
        assert metrics.safety_violations == 2


class TestTracing:
    def test_tracer_creates_spans_with_parent_child(self) -> None:
        tracer = OpenTelemetryTracer()
        trace = tracer.start_trace("eval-run")
        assert trace.trace_id
        assert len(trace.spans) == 1

        parent = trace.spans[0]
        child = tracer.start_span("run-scenario")
        assert child.parent_id == parent.span_id

        tracer.end_span(child)
        tracer.end_span(parent)

        assert child.end_time is not None
        assert parent.end_time is not None
        assert child.start_time <= child.end_time
        assert len(trace.spans) == 2

    def test_trace_context_has_valid_trace_id(self) -> None:
        tracer = OpenTelemetryTracer()
        trace = tracer.start_trace("eval-run")
        assert trace.trace_id
        assert len(trace.trace_id) == 32
        assert all(c in "0123456789abcdef" for c in trace.trace_id)

    def test_multiple_traces_are_independent(self) -> None:
        tracer = OpenTelemetryTracer()
        t1 = tracer.start_trace("run-1")
        _span = tracer.start_span("step")
        tracer.end_span(_span)

        tracer2 = OpenTelemetryTracer()
        t2 = tracer2.start_trace("run-2")

        assert t1.trace_id != t2.trace_id

    def test_span_events(self) -> None:
        tracer = OpenTelemetryTracer()
        trace = tracer.start_trace("eval-run")
        span = trace.spans[0]
        tracer.add_event(span, "cache-miss", {"key": "sc-1"})
        tracer.add_event(span, "judge-call")
        assert len(span.events) == 2
        assert span.events[0]["name"] == "cache-miss"
        assert span.events[0]["attributes"] == {"key": "sc-1"}

    def test_set_attribute(self) -> None:
        tracer = OpenTelemetryTracer()
        trace = tracer.start_trace("eval-run")
        span = trace.spans[0]
        tracer.set_attribute(span, "agent.type", "python")
        tracer.set_attribute(span, "scenarios.count", 20)
        assert span.attributes["agent.type"] == "python"
        assert span.attributes["scenarios.count"] == 20

    def test_to_dict_skips_unfinished_spans(self) -> None:
        tracer = OpenTelemetryTracer()
        tracer.start_trace("eval-run")
        _finished = tracer.start_span("step-1")
        tracer.end_span(_finished)
        _unfinished = tracer.start_span("step-2")
        d = tracer.to_dict()
        assert len(d["spans"]) == 3
        finished = [s for s in d["spans"] if s["name"] == "step-1"]
        unfinished = [s for s in d["spans"] if s["name"] == "step-2"]
        assert finished[0]["end_time"] is not None
        assert unfinished[0]["end_time"] is None
        assert unfinished[0]["duration_ms"] is None

    def test_export_otlp_no_crash_on_bad_endpoint(self) -> None:
        tracer = OpenTelemetryTracer()
        tracer.start_trace("eval-run")
        tracer.export_otlp("http://localhost:19999/v1/traces")
