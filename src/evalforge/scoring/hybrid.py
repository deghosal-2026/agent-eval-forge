"""Hybrid scorer — deterministic gate first, judge fallback on inconclusive.

A HybridScorer wraps a deterministic gate scorer and a judge scorer. The
scoring flow is:

1. Run the deterministic gate scorer first (cheap, fast).
2. If the gate clearly passes (score >= threshold), return that result.
3. If the gate clearly fails (score == 0.0), return that result.
4. Otherwise (inconclusive), fall back to the LLM-as-judge scorer.

This hybrid approach ensures safety-critical checks always run through a
deterministic gate before resorting to an LLM judge, while avoiding
unnecessary judge calls for clear-cut cases.

Metric names must match a registered judge scorer in the SCORERS registry.
The judge client is injected at construction time.
"""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.registry import get_scorer
from evalforge.scoring.result import ScoreResult


class HybridScorer:
    """A wrapper that runs a deterministic gate, then falls back to a judge scorer.

    The gate is evaluated first. If its result is decisive (score >= threshold
    or score == 0.0) that result is returned immediately. Otherwise the judge
    scorer is invoked for a semantic evaluation.

    Args:
        metric_name: The metric name to resolve in the scorer registry for
            the judge fallback phase.
        gate: A Scorer instance (or class) that implements the deterministic
            gate. If a class is passed, it is instantiated with no args.
        judge: A JudgeClient instance used when the gate result is
            inconclusive (not clearly passed or failed).
    """

    def __init__(self, metric_name: str, gate: Scorer, judge: JudgeClient) -> None:
        self.metric_name = metric_name
        self.gate = gate() if isinstance(gate, type) else gate
        self.judge = judge

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        """Score an artifact using the hybrid approach.

        Resolution order:
        1. Load (or lazily initialize) the judge scorer from the registry.
        2. Run the deterministic gate.
        3. If gate score >= threshold or gate score == 0.0 — return gate result.
        4. Otherwise — inject the judge client into the judge scorer and
           delegate to it for a semantic evaluation.

        Args:
            artifact: The run artifact to score.
            scenario: The scenario definition with expectations and metrics.
            metric_config: Configuration dict from the scenario's metric
                definition (typically includes "threshold").

        Returns:
            A ScoreResult from either the deterministic gate or the judge.
        """
        judge_scorer = getattr(self, "_judge_scorer", None)
        if judge_scorer is None:
            judge_scorer_cls = get_scorer(self.metric_name)
            if judge_scorer_cls is None:
                raise ValueError(f"no judge scorer registered for: {self.metric_name}")
            judge_scorer = judge_scorer_cls()
            self._judge_scorer = judge_scorer
        gate_result = self.gate.score(artifact, scenario, metric_config)
        threshold = metric_config.get("threshold", 0.5)
        # Deterministic gate clearly passes — short-circuit, avoid judge cost
        if gate_result.score is not None and gate_result.score >= threshold:
            return gate_result
        # Deterministic gate clearly fails — also short-circuit
        if gate_result.score is not None and gate_result.score == 0.0:
            return gate_result
        # Inconclusive — fall back to judge
        judge_scorer.judge = self.judge  # type: ignore[union-attr]
        return judge_scorer.score(artifact, scenario, metric_config)
