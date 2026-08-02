"""Tests for the failure taxonomy and analytics module."""

from evalforge.analytics.taxonomy import (
    AnalyticsReport,
    FailureCategory,
    FailureTaxonomy,
    classify_failure,
)
from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult


def _sr(name: str, passed: bool, score: float = 0.0) -> ScoreResult:
    return ScoreResult(
        metric=name,
        score=score,
        threshold=0.8,
        passed=passed,
        category="correctness",
        blocking=False,
        detail={},
        source="deterministic",
        error=None,
    )


def _ss(
    scenario_id: str,
    status: str,
    metrics: dict | None = None,
    safety_violations: list | None = None,
) -> ScenarioScore:
    return ScenarioScore(
        scenario_id=scenario_id,
        metric_results=metrics or {},
        status=status,
        safety_violations=safety_violations or [],
    )


def _rs(scenario_scores: dict[str, ScenarioScore]) -> RunScore:
    passed = sum(1 for s in scenario_scores.values() if s.status == "passed")
    failed = sum(1 for s in scenario_scores.values() if s.status == "failed")
    warned = sum(1 for s in scenario_scores.values() if s.status == "warn")
    return RunScore(
        scenario_scores=scenario_scores,
        totals={"passed": passed, "warned": warned, "failed": failed},
        safety_violations=[],
        exit_code=0,
    )


class TestClassifyFailure:
    def test_passed_scenario_returns_none(self) -> None:
        ss = _ss("sc-1", "passed")
        assert FailureTaxonomy.classify(ss) is None
        assert classify_failure(ss) is None

    def test_safety_violation(self) -> None:
        ss = _ss("sc-1", "failed", safety_violations=["disallowed_tool: rm"])
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.SAFETY_VIOLATION
        assert result.severity == "critical"
        assert result.scenario_id == "sc-1"
        assert "disallowed_tool: rm" in result.description

    def test_tool_error_tool_correctness(self) -> None:
        ss = _ss(
            "sc-2",
            "failed",
            metrics={
                "tool_correctness": _sr("tool_correctness", passed=False, score=0.0),
                "argument_correctness": _sr("argument_correctness", passed=True),
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.TOOL_ERROR
        assert result.metric_name == "tool_correctness"
        assert result.severity == "medium"

    def test_argument_error(self) -> None:
        ss = _ss(
            "sc-3",
            "failed",
            metrics={
                "tool_correctness": _sr("tool_correctness", passed=True),
                "argument_correctness": _sr(
                    "argument_correctness", passed=False, score=0.4
                ),
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.ARGUMENT_ERROR
        assert result.metric_name == "argument_correctness"
        assert result.score == 0.4

    def test_schema_error(self) -> None:
        ss = _ss(
            "sc-4",
            "failed",
            metrics={"schema_validity": _sr("schema_validity", passed=False)},
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.SCHEMA_ERROR
        assert result.metric_name == "schema_validity"

    def test_budget_exceeded(self) -> None:
        ss = _ss(
            "sc-5",
            "failed",
            metrics={"step_efficiency": _sr("step_efficiency", passed=False)},
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.BUDGET_EXCEEDED

    def test_cost_budget_adherence_fails(self) -> None:
        ss = _ss(
            "sc-6",
            "failed",
            metrics={
                "cost_budget_adherence": _sr(
                    "cost_budget_adherence", passed=False, score=0.1
                ),
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.BUDGET_EXCEEDED
        assert result.metric_name == "cost_budget_adherence"
        assert result.severity == "medium"

    def test_policy_violation_zero_disallowed(self) -> None:
        ss = _ss(
            "sc-7",
            "failed",
            metrics={
                "tool_correctness": _sr("tool_correctness", passed=True),
                "zero_disallowed_actions": _sr(
                    "zero_disallowed_actions", passed=False, score=0.0
                ),
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.POLICY_VIOLATION
        assert result.severity == "critical"

    def test_retry_exhausted(self) -> None:
        ss = _ss(
            "sc-8",
            "failed",
            metrics={
                "retry_discipline_gate": _sr(
                    "retry_discipline_gate", passed=False, score=0.0
                ),
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.RETRY_EXHAUSTED
        assert result.severity == "low"

    def test_incorrect_output(self) -> None:
        ss = _ss(
            "sc-9",
            "failed",
            metrics={
                "task_completion": _sr("task_completion", passed=False, score=0.3)
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.INCORRECT_OUTPUT

    def test_unknown_failure(self) -> None:
        ss = _ss("sc-10", "failed")
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.UNKNOWN
        assert result.severity == "low"

    def test_safety_before_tool_error(self) -> None:
        ss = _ss(
            "sc-11",
            "failed",
            safety_violations=["danger"],
            metrics={
                "tool_correctness": _sr("tool_correctness", passed=False),
            },
        )
        result = FailureTaxonomy.classify(ss)
        assert result is not None
        assert result.category == FailureCategory.SAFETY_VIOLATION


class TestAnalyze:
    def test_empty_run_all_pass(self) -> None:
        rs = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss("sc-2", "passed"),
                "sc-3": _ss("sc-3", "passed"),
            }
        )
        report = FailureTaxonomy.analyze(rs)
        assert report.total_scenarios == 3
        assert report.passed == 3
        assert report.failed == 0
        assert report.warnings == 0
        assert report.pass_rate == 1.0
        assert report.failure_breakdown == {}
        assert report.severity_breakdown == {}
        assert report.top_failing_scenarios == []

    def test_mixed_pass_fail(self) -> None:
        rs = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss(
                    "sc-2",
                    "failed",
                    metrics={"tool_correctness": _sr("tool_correctness", passed=False)},
                ),
                "sc-3": _ss("sc-3", "passed"),
                "sc-4": _ss(
                    "sc-4",
                    "failed",
                    metrics={
                        "argument_correctness": _sr(
                            "argument_correctness", passed=False, score=0.2
                        )
                    },
                ),
                "sc-5": _ss("sc-5", "warn", safety_violations=["bad"]),
            }
        )
        report = FailureTaxonomy.analyze(rs)
        assert report.total_scenarios == 5
        assert report.passed == 2
        assert report.failed == 2
        assert report.warnings == 1
        assert report.pass_rate == 0.4
        assert FailureCategory.TOOL_ERROR.value in report.failure_breakdown
        assert FailureCategory.ARGUMENT_ERROR.value in report.failure_breakdown
        assert FailureCategory.SAFETY_VIOLATION.value in report.failure_breakdown
        assert "critical" in report.severity_breakdown
        assert "medium" in report.severity_breakdown

    def test_recommendations_generated(self) -> None:
        rs = _rs(
            {
                "sc-1": _ss(
                    "sc-1",
                    "failed",
                    metrics={"tool_correctness": _sr("tool_correctness", passed=False)},
                ),
                "sc-2": _ss(
                    "sc-2", "failed", safety_violations=["critical_issue"]
                ),
                "sc-3": _ss(
                    "sc-3",
                    "failed",
                    metrics={"schema_validity": _sr("schema_validity", passed=False)},
                ),
            }
        )
        report = FailureTaxonomy.analyze(rs)
        assert len(report.recommendations) >= 3
        assert any("safety" in r.lower() for r in report.recommendations)
        assert any("tool" in r.lower() for r in report.recommendations)
        assert any("schema" in r.lower() for r in report.recommendations)

    def test_report_structure(self) -> None:
        rs = _rs({})
        report = FailureTaxonomy.analyze(rs)
        assert isinstance(report, AnalyticsReport)
        assert isinstance(report.pass_rate, float)
        assert isinstance(report.failure_breakdown, dict)
        assert isinstance(report.severity_breakdown, dict)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.top_failing_scenarios, list)


class TestCompareTaxonomy:
    def test_compare_identical_runs(self) -> None:
        rs = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss("sc-2", "passed"),
            }
        )
        result = FailureTaxonomy.compare_taxonomy(rs, rs)
        assert result["total_delta"] == 0
        assert result["new_categories"] == []
        assert result["resolved_categories"] == []

    def test_compare_new_failures(self) -> None:
        baseline = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss("sc-2", "passed"),
            }
        )
        current = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss(
                    "sc-2",
                    "failed",
                    metrics={
                        "tool_correctness": _sr("tool_correctness", passed=False)
                    },
                ),
            }
        )
        result = FailureTaxonomy.compare_taxonomy(current, baseline)
        assert result["total_failures_current"] == 1
        assert result["total_failures_baseline"] == 0
        assert result["total_delta"] == 1
        assert result["new_categories"] == ["tool_error"]

    def test_compare_resolved_failures(self) -> None:
        baseline = _rs(
            {
                "sc-1": _ss(
                    "sc-1",
                    "failed",
                    metrics={
                        "argument_correctness": _sr(
                            "argument_correctness", passed=False
                        )
                    },
                ),
            }
        )
        current = _rs({"sc-1": _ss("sc-1", "passed")})
        result = FailureTaxonomy.compare_taxonomy(current, baseline)
        assert result["total_failures_current"] == 0
        assert result["total_failures_baseline"] == 1
        assert result["total_delta"] == -1
        assert result["resolved_categories"] == ["argument_error"]

    def test_compare_mixed_changes(self) -> None:
        baseline = _rs(
            {
                "sc-1": _ss(
                    "sc-1",
                    "failed",
                    metrics={"tool_correctness": _sr("tool_correctness", passed=False)},
                ),
                "sc-2": _ss(
                    "sc-2",
                    "failed",
                    metrics={"schema_validity": _sr("schema_validity", passed=False)},
                ),
            }
        )
        current = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss(
                    "sc-2",
                    "failed",
                    metrics={"schema_validity": _sr("schema_validity", passed=False)},
                ),
                "sc-3": _ss(
                    "sc-3",
                    "failed",
                    metrics={
                        "step_efficiency": _sr("step_efficiency", passed=False)
                    },
                ),
            }
        )
        result = FailureTaxonomy.compare_taxonomy(current, baseline)
        assert result["total_failures_current"] == 2
        assert result["total_failures_baseline"] == 2
        assert result["total_delta"] == 0
        assert result["resolved_categories"] == ["tool_error"]
        assert "budget_exceeded" in result["deltas"]
        assert result["deltas"]["budget_exceeded"] == 1
        assert result["deltas"]["tool_error"] == -1

    def test_compare_delta_breakdown(self) -> None:
        baseline = _rs(
            {
                "sc-1": _ss(
                    "sc-1",
                    "failed",
                    metrics={
                        "step_efficiency": _sr("step_efficiency", passed=False)
                    },
                ),
            }
        )
        current = _rs(
            {
                "sc-1": _ss(
                    "sc-1",
                    "failed",
                    metrics={
                        "step_efficiency": _sr("step_efficiency", passed=False)
                    },
                ),
                "sc-2": _ss(
                    "sc-2",
                    "failed",
                    metrics={
                        "cost_budget_adherence": _sr(
                            "cost_budget_adherence", passed=False
                        )
                    },
                ),
                "sc-3": _ss(
                    "sc-3",
                    "failed",
                    metrics={
                        "cost_budget_adherence": _sr(
                            "cost_budget_adherence", passed=False
                        )
                    },
                ),
            }
        )
        result = FailureTaxonomy.compare_taxonomy(current, baseline)
        assert result["total_failures_current"] == 3
        assert result["total_failures_baseline"] == 1
        assert result["total_delta"] == 2

    def test_compare_all_passed(self) -> None:
        baseline = _rs({"sc-1": _ss("sc-1", "failed")})
        current = _rs(
            {
                "sc-1": _ss("sc-1", "passed"),
                "sc-2": _ss("sc-2", "passed"),
            }
        )
        result = FailureTaxonomy.compare_taxonomy(current, baseline)
        assert result["total_failures_current"] == 0
        assert result["total_failures_baseline"] == 1
        assert result["total_delta"] == -1
        assert result["resolved_categories"] == ["unknown"]
