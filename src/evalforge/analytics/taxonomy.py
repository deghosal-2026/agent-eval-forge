"""Failure classification and analytics for evaluation runs.

Public API:

- :func:`classify_failure` — classify a single scenario score.
- :class:`FailureTaxonomy` — static methods for batch analysis and comparison.
- :class:`AnalyticsReport` — structured report of run-wide health.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from evalforge.scoring.result import RunScore, ScenarioScore


class FailureCategory(Enum):
    """Taxonomic categories for evaluation failures.

    Each failure is assigned one category based on its root cause.
    Severity levels are mapped in :data:`_SEVERITY_MAP`.
    """

    SAFETY_VIOLATION = "safety_violation"
    TOOL_ERROR = "tool_error"
    ARGUMENT_ERROR = "argument_error"
    SCHEMA_ERROR = "schema_error"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    AGENT_CRASH = "agent_crash"
    HALLUCINATION = "hallucination"
    INCORRECT_OUTPUT = "incorrect_output"
    INCOMPLETE_OUTPUT = "incomplete_output"
    RETRY_EXHAUSTED = "retry_exhausted"
    POLICY_VIOLATION = "policy_violation"
    UNKNOWN = "unknown"


# Severity mapping for each failure category.
# Used to prioritize recommendations in analytics reports.
_SEVERITY_MAP: dict[FailureCategory, str] = {
    FailureCategory.SAFETY_VIOLATION: "critical",
    FailureCategory.POLICY_VIOLATION: "critical",
    FailureCategory.AGENT_CRASH: "high",
    FailureCategory.TIMEOUT: "high",
    FailureCategory.HALLUCINATION: "high",
    FailureCategory.TOOL_ERROR: "medium",
    FailureCategory.ARGUMENT_ERROR: "medium",
    FailureCategory.SCHEMA_ERROR: "medium",
    FailureCategory.BUDGET_EXCEEDED: "medium",
    FailureCategory.RETRY_EXHAUSTED: "low",
    FailureCategory.INCORRECT_OUTPUT: "low",
    FailureCategory.INCOMPLETE_OUTPUT: "low",
    FailureCategory.UNKNOWN: "low",
}

# Mapping of metric names to their most likely failure category.
# Used during classification when a metric fails but there is no
# safety/policy violation context.
_METRIC_CATEGORIES: dict[str, FailureCategory] = {
    "tool_correctness": FailureCategory.TOOL_ERROR,
    "tool_called": FailureCategory.TOOL_ERROR,
    "zero_disallowed_actions": FailureCategory.POLICY_VIOLATION,
    "unsafe_action_avoidance": FailureCategory.SAFETY_VIOLATION,
    "argument_correctness": FailureCategory.ARGUMENT_ERROR,
    "schema_validity": FailureCategory.SCHEMA_ERROR,
    "field_correctness": FailureCategory.SCHEMA_ERROR,
    "step_efficiency": FailureCategory.BUDGET_EXCEEDED,
    "cost_budget_adherence": FailureCategory.BUDGET_EXCEEDED,
    "policy_adherence_gate": FailureCategory.POLICY_VIOLATION,
    "retry_discipline_gate": FailureCategory.RETRY_EXHAUSTED,
    "task_completion": FailureCategory.INCORRECT_OUTPUT,
    "output_accuracy": FailureCategory.INCORRECT_OUTPUT,
    "hallucination": FailureCategory.HALLUCINATION,
}


@dataclass
class FailureClassification:
    """A single classified failure with severity and context.

    Attributes:
        category: The failure category from :class:`FailureCategory`.
        severity: Human-readable severity level (critical/high/medium/low).
        description: Human-readable description of the failure.
        scenario_id: The scenario that produced this failure.
        metric_name: The specific metric that failed (if applicable).
        score: The numeric score that triggered the failure (if applicable).
        details: Additional context dict from the scoring result.
    """

    category: FailureCategory
    severity: str
    description: str
    scenario_id: str
    metric_name: str | None = None
    score: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _make_classification(
    category: FailureCategory,
    description: str,
    scenario_id: str,
    metric_name: str | None = None,
    score: float | None = None,
    details: dict[str, Any] | None = None,
) -> FailureClassification:
    """Build a :class:`FailureClassification` with severity looked up from :data:`_SEVERITY_MAP`.

    Args:
        category: The failure category.
        description: Human-readable description.
        scenario_id: The scenario identifier.
        metric_name: Optional metric name.
        score: Optional failure score.
        details: Optional additional context.

    Returns:
        A fully populated :class:`FailureClassification`.
    """
    return FailureClassification(
        category=category,
        severity=_SEVERITY_MAP.get(category, "low"),
        description=description,
        scenario_id=scenario_id,
        metric_name=metric_name,
        score=score,
        details=details or {},
    )


@dataclass
class AnalyticsReport:
    """Aggregated analytics for an entire evaluation run.

    Attributes:
        total_scenarios: Number of scenarios evaluated.
        passed: Scenarios that passed all checks.
        failed: Scenarios with at least one failing metric.
        warnings: Scenarios with a ``"warn"`` status.
        pass_rate: Fraction of scenarios that passed.
        failure_breakdown: Count of failures per :class:`FailureCategory`.
        severity_breakdown: Count of failures per severity level.
        top_failing_scenarios: List of ``(scenario_id, failure_count)`` tuples.
        recommendations: Human-readable action items.
    """

    total_scenarios: int
    passed: int
    failed: int
    warnings: int
    pass_rate: float
    failure_breakdown: dict[str, int]
    severity_breakdown: dict[str, int]
    top_failing_scenarios: list[tuple[str, int]]
    recommendations: list[str]


class FailureTaxonomy:
    """Classifies evaluation failures into a structured taxonomy.

    Provides static methods for single-scenario classification, full-run
    analytics, and run-vs-run taxonomy comparison.
    """

    @staticmethod
    def classify(scenario_score: ScenarioScore) -> FailureClassification | None:
        """Classify a single scenario score into the taxonomy.

        Returns ``None`` when the scenario passed cleanly.
        Returns a :class:`FailureClassification` describing the primary
        failure when the scenario failed or warned.

        Classification priority (first match wins):

        1. Safety violations on the :attr:`ScenarioScore.safety_violations`.
        2. Safety-related metric failures (``zero_disallowed_actions``,
           ``unsafe_action_avoidance``, ``policy_adherence_gate``).
        3. Core metric failures mapped via :data:`_METRIC_CATEGORIES`.
        4. Unknown failures when no specific metric is identified.

        Args:
            scenario_score: The scenario score to classify.

        Returns:
            A :class:`FailureClassification` or ``None`` if passed.
        """
        if scenario_score.status == "passed":
            return None

        if scenario_score.safety_violations:
            return _make_classification(
                FailureCategory.SAFETY_VIOLATION,
                f"Safety violations: {', '.join(scenario_score.safety_violations)}",
                scenario_score.scenario_id,
                metric_name="safety_violations",
                details={"violations": scenario_score.safety_violations},
            )

        safety_metrics = {
            "zero_disallowed_actions": FailureCategory.POLICY_VIOLATION,
            "unsafe_action_avoidance": FailureCategory.SAFETY_VIOLATION,
            "policy_adherence_gate": FailureCategory.POLICY_VIOLATION,
        }
        for metric_name, category in safety_metrics.items():
            result = scenario_score.metric_results.get(metric_name)
            if result is not None and result.passed is False:
                return _make_classification(
                    category,
                    f"Safety/policy metric '{metric_name}' failed (score={result.score})",
                    scenario_score.scenario_id,
                    metric_name=metric_name,
                    score=result.score,
                    details=dict(result.detail),
                )

        priority_categories: list[tuple[str, FailureCategory]] = [
            ("tool_correctness", FailureCategory.TOOL_ERROR),
            ("tool_called", FailureCategory.TOOL_ERROR),
            ("argument_correctness", FailureCategory.ARGUMENT_ERROR),
            ("schema_validity", FailureCategory.SCHEMA_ERROR),
            ("field_correctness", FailureCategory.SCHEMA_ERROR),
            ("step_efficiency", FailureCategory.BUDGET_EXCEEDED),
            ("cost_budget_adherence", FailureCategory.BUDGET_EXCEEDED),
            ("retry_discipline_gate", FailureCategory.RETRY_EXHAUSTED),
            ("task_completion", FailureCategory.INCORRECT_OUTPUT),
            ("output_accuracy", FailureCategory.INCORRECT_OUTPUT),
            ("hallucination", FailureCategory.HALLUCINATION),
        ]
        for metric_name, category in priority_categories:
            result = scenario_score.metric_results.get(metric_name)
            if result is not None and result.passed is False:
                return _make_classification(
                    category,
                    f"Metric '{metric_name}' failed (score={result.score})",
                    scenario_score.scenario_id,
                    metric_name=metric_name,
                    score=result.score,
                    details=dict(result.detail),
                )

        if scenario_score.metric_results:
            for name, result in scenario_score.metric_results.items():
                if result.passed is False:
                    fallback = _METRIC_CATEGORIES.get(name, FailureCategory.UNKNOWN)
                    return _make_classification(
                        fallback,
                        f"Metric '{name}' failed (score={result.score})",
                        scenario_score.scenario_id,
                        metric_name=name,
                        score=result.score,
                        details=dict(result.detail),
                    )

        return _make_classification(
            FailureCategory.UNKNOWN,
            f"Scenario '{scenario_score.scenario_id}' failed "
            f"with status '{scenario_score.status}', "
            "no failing metrics identified",
            scenario_score.scenario_id,
        )

    @staticmethod
    def analyze(run_score: RunScore) -> AnalyticsReport:
        """Produce an analytics report from a run score.

        Iterates every scenario, classifies failures, and builds a
        structured report with breakdowns, severity counts, and
        actionable recommendations.

        Args:
            run_score: The run score to analyze.

        Returns:
            An :class:`AnalyticsReport` with aggregated metrics.
        """
        classifications: list[FailureClassification] = []
        passed = 0
        failed = 0
        warnings = 0
        scenario_failure_counts: dict[str, int] = {}

        for sid, scenario_score in run_score.scenario_scores.items():
            if scenario_score.status == "passed":
                passed += 1
                continue
            if scenario_score.status == "warn":
                warnings += 1
            else:
                failed += 1

            classification = FailureTaxonomy.classify(scenario_score)
            if classification is not None:
                classifications.append(classification)
                scenario_failure_counts[sid] = scenario_failure_counts.get(sid, 0) + 1

        total = len(run_score.scenario_scores) or 1
        pass_rate = passed / total

        category_counts: dict[str, int] = dict(
            Counter(c.category.value for c in classifications)
        )
        severity_counts: dict[str, int] = dict(
            Counter(c.severity for c in classifications)
        )
        top_failing = sorted(
            scenario_failure_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        recommendations: list[str] = []
        _build_recommendations(classifications, recommendations)

        return AnalyticsReport(
            total_scenarios=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            pass_rate=pass_rate,
            failure_breakdown=category_counts,
            severity_breakdown=severity_counts,
            top_failing_scenarios=top_failing,
            recommendations=recommendations,
        )

    @staticmethod
    def compare_taxonomy(
        current_run: RunScore, baseline_run: RunScore
    ) -> dict[str, Any]:
        """Compare failure taxonomy between two runs.

        Returns a dict with keys describing how the failure profile changed:

        - ``current_breakdown``: :class:`FailureCategory` counts for the
          current run.
        - ``baseline_breakdown``: :class:`FailureCategory` counts for the
          baseline run.
        - ``deltas``: Per-category difference (current minus baseline).
        - ``new_categories``: Categories present in current but absent in
          baseline.
        - ``resolved_categories``: Categories present in baseline but
          absent in current.
        - ``total_failures_current``, ``total_failures_baseline``,
          ``total_delta``: Total failure count comparisons.

        Args:
            current_run: The current (new) run score.
            baseline_run: The baseline run score to compare against.

        Returns:
            A dict with taxonomy comparison data.
        """
        current_classes = [
            c
            for score in current_run.scenario_scores.values()
            if (c := FailureTaxonomy.classify(score)) is not None
        ]
        baseline_classes = [
            c
            for score in baseline_run.scenario_scores.values()
            if (c := FailureTaxonomy.classify(score)) is not None
        ]

        current_counts: dict[str, int] = dict(
            Counter(c.category.value for c in current_classes)
        )
        baseline_counts: dict[str, int] = dict(
            Counter(c.category.value for c in baseline_classes)
        )

        all_categories = set(current_counts) | set(baseline_counts)
        deltas = {
            cat: current_counts.get(cat, 0) - baseline_counts.get(cat, 0)
            for cat in all_categories
        }
        new_categories = sorted(
            set(current_counts) - set(baseline_counts)
        )
        resolved_categories = sorted(
            set(baseline_counts) - set(current_counts)
        )

        return {
            "current_breakdown": current_counts,
            "baseline_breakdown": baseline_counts,
            "deltas": deltas,
            "new_categories": new_categories,
            "resolved_categories": resolved_categories,
            "total_failures_current": len(current_classes),
            "total_failures_baseline": len(baseline_classes),
            "total_delta": len(current_classes) - len(baseline_classes),
        }


def classify_failure(scenario_score: ScenarioScore) -> FailureClassification | None:
    """Convenience wrapper for :meth:`FailureTaxonomy.classify`.

    Args:
        scenario_score: The scenario score to classify.

    Returns:
        A :class:`FailureClassification` or ``None`` if passed.
    """
    return FailureTaxonomy.classify(scenario_score)


def _build_recommendations(
    classifications: list[FailureClassification],
    recommendations: list[str],
) -> None:
    """Generate human-readable recommendations from classified failures.

    Iterates over the failure category counts and appends targeted
    remediation suggestions to the recommendations list.

    Args:
        classifications: List of classified failures.
        recommendations: List to append recommendation strings to.
    """
    category_counts = Counter(c.category for c in classifications)

    if FailureCategory.SAFETY_VIOLATION in category_counts:
        recommendations.append(
            f"Address {category_counts[FailureCategory.SAFETY_VIOLATION]} safety violations: "
            "audit disallowed-tool configuration and unsafe-action detection."
        )
    if FailureCategory.POLICY_VIOLATION in category_counts:
        recommendations.append(
            f"Address {category_counts[FailureCategory.POLICY_VIOLATION]} policy violations: "
            "review tool allow/deny lists and policy gate rules."
        )
    if FailureCategory.TOOL_ERROR in category_counts:
        recommendations.append(
            f"Fix {category_counts[FailureCategory.TOOL_ERROR]} tool errors: "
            "ensure the agent uses correct tool names and calls all required tools."
        )
    if FailureCategory.ARGUMENT_ERROR in category_counts:
        recommendations.append(
            f"Fix {category_counts[FailureCategory.ARGUMENT_ERROR]} argument errors: "
            "verify the agent passes correct arguments to tool calls."
        )
    if FailureCategory.SCHEMA_ERROR in category_counts:
        recommendations.append(
            f"Fix {category_counts[FailureCategory.SCHEMA_ERROR]} schema errors: "
            "ensure the agent output conforms to the expected JSON schema."
        )
    if FailureCategory.BUDGET_EXCEEDED in category_counts:
        recommendations.append(
            f"Optimize {category_counts[FailureCategory.BUDGET_EXCEEDED]} budget overruns: "
            "reduce agent step count or cost per scenario."
        )
    if FailureCategory.INCORRECT_OUTPUT in category_counts:
        recommendations.append(
            f"Correct {category_counts[FailureCategory.INCORRECT_OUTPUT]} incorrect outputs: "
            "verify agent final answers match expected values."
        )
    if FailureCategory.RETRY_EXHAUSTED in category_counts:
        recommendations.append(
            f"Investigate {category_counts[FailureCategory.RETRY_EXHAUSTED]} retry-exhausted "
            "scenarios: the agent may be looping on a stubborn tool call."
        )
    if failure_count := sum(category_counts.values()):
        recommendations.append(
            f"Review {failure_count} total failure(s) in priority order "
            "(critical -> low) for maximum impact."
        )
