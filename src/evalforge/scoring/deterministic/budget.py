"""Deterministic scorers for budget-adherence metrics.

Provides two efficiency-oriented scorers:

- :class:`StepEfficiencyScorer` — penalizes agents that exceed the maximum
  allowed number of steps.
- :class:`CostBudgetAdherenceScorer` — penalizes agents whose total cost
  exceeds the maximum allowed budget in USD.
"""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult


@register_scorer
class StepEfficiencyScorer(Scorer):
    """Score the agent's step efficiency against a budget.

    Computes a score that decays linearly as the agent exceeds ``max_steps``.

    - score = 1.0 when steps <= max_steps.
    - score decays toward 0.0 as steps exceed max_steps.
    - score = 1.0 when no budget is declared (no-op).

    Attributes:
        name: ``"step_efficiency"``
        category: ``"efficiency"``
    """
    name = "step_efficiency"
    category = "efficiency"

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        budget = scenario.budget
        max_steps = budget.max_steps if budget else None
        total = len(artifact.trajectory or [])
        if max_steps is None or max_steps <= 0:
            score = 1.0
        else:
            score = max(0.0, 1.0 - max(0, total - max_steps) / max_steps)
        threshold = metric_config.get("threshold", 0.7)
        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            category=self.category,
            blocking=False,
            detail={"steps": total, "max_steps": max_steps},
            source="deterministic",
            error=None,
        )


@register_scorer
class CostBudgetAdherenceScorer(Scorer):
    """Score the agent's cost adherence against a USD budget.

    Computes a score that decays linearly as cost exceeds ``max_cost_usd``.

    - score = 1.0 when actual cost <= max_cost_usd.
    - score decays toward 0.0 as cost exceeds the budget.
    - score = 1.0 when no budget is declared (no-op).

    Attributes:
        name: ``"cost_budget_adherence"``
        category: ``"efficiency"``
    """
    name = "cost_budget_adherence"
    category = "efficiency"

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        budget = scenario.budget
        max_cost = budget.max_cost_usd if budget else None
        actual = artifact.cost.cost_usd if artifact.cost else 0.0
        actual = actual or 0.0
        if max_cost is None or max_cost <= 0:
            score = 1.0
        else:
            ratio = actual / max_cost
            score = max(0.0, 1.0 - max(0.0, ratio - 1.0))
        threshold = metric_config.get("threshold", 0.7)
        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            category=self.category,
            blocking=False,
            detail={"actual_cost_usd": actual, "max_cost_usd": max_cost},
            source="deterministic",
            error=None,
        )
