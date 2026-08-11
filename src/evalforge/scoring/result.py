"""Scoring result models.

Defines the dataclasses that carry scoring output through the pipeline:

- :class:`ScoreResult` — a single metric evaluation (score, pass/fail, detail).
- :class:`ScenarioScore` — aggregate of all metrics for one scenario.
- :class:`RunScore` — aggregate of all scenarios across a run.
- :class:`JudgeVerdict` — raw output from an LLM-as-judge call.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoreResult:
    """The result of evaluating a single metric against a run artifact.

    Attributes:
        metric: The metric name (e.g. ``"tool_correctness"``).
        score: Numeric score in [0.0, 1.0], or None if scoring failed.
        threshold: Minimum score required to pass.
        passed: Whether the score meets the threshold. None if scoring failed.
        category: One of ``"safety"``, ``"correctness"``, or ``"efficiency"``.
        blocking: If True and passed is False, the scenario is marked failed
            regardless of other metrics.
        detail: Arbitrary metadata about the evaluation (e.g. matched
            expectations, violation lists, rationale from judge).
        source: ``"deterministic"`` or ``"judge"`` — how the score was produced.
        error: Error message if scoring failed; None otherwise.
    """
    metric: str
    score: float | None
    threshold: float | None
    passed: bool | None
    category: str  # "safety" | "correctness" | "efficiency"
    blocking: bool
    detail: dict[str, object]
    source: str  # "deterministic" | "judge"
    error: str | None


@dataclass
class ScenarioScore:
    """Aggregate of all metric results for a single scenario.

    Attributes:
        scenario_id: Unique identifier matching the scenario definition.
        metric_results: Mapping of metric name to its ScoreResult.
        status: Overall status — ``"passed"``, ``"warn"``, or ``"failed"``.
            A scenario is ``"failed"`` if any safety violation exists or any
            blocking metric failed. It is ``"warn"`` if a non-blocking metric
            failed but no blocking metrics did.
        safety_violations: List of metric names that triggered a safety
            category failure. Presence forces overall status to ``"failed"``.
    """
    scenario_id: str
    metric_results: dict[str, ScoreResult]
    status: str  # "passed" | "warn" | "failed"
    safety_violations: list[str]


@dataclass
class RunScore:
    """Aggregate of all scenario scores across an entire run.

    Attributes:
        scenario_scores: Mapping of scenario_id to ScenarioScore.
        totals: Counts of passed/warned/failed scenarios.
        safety_violations: Union of all safety violations across scenarios.
        exit_code: Process exit code — 0 (all passed), 1 (failures), 3 (judge
            errors), 4 (safety violation).
        dimensions: Three independent score dimensions computed across all
            scenarios: ``compatibility``, ``safety``, and ``quality``, each in
            [0.0, 1.0]. Added by ``ScoringEngine._compute_dimensions()``.
    """
    scenario_scores: dict[str, ScenarioScore]
    totals: dict[str, int]  # {"passed": int, "warned": int, "failed": int}
    safety_violations: list[str]
    exit_code: int  # 0 | 1 | 2 | 3 | 4
    dimensions: dict[str, float] = field(default_factory=dict)


@dataclass
class JudgeVerdict:
    """Raw output from an LLM-as-judge call.

    Attributes:
        score: Numeric judgment in [0.0, 1.0].
        rationale: Free-text explanation from the judge model.
    """
    score: float
    rationale: str
