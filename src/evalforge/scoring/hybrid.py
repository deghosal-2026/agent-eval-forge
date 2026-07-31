"""Hybrid scorer — deterministic gate first, judge fallback on inconclusive."""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.registry import get_scorer
from evalforge.scoring.result import ScoreResult


class HybridScorer:
    """A wrapper that runs a deterministic gate, then falls back to a judge scorer."""

    def __init__(self, metric_name: str, gate: Scorer, judge: JudgeClient) -> None:
        self.metric_name = metric_name
        self.gate = gate() if isinstance(gate, type) else gate
        self.judge = judge

    def score(self, artifact: RunArtifact, scenario: Scenario,
              metric_config: dict[str, Any]) -> ScoreResult:
        judge_scorer = getattr(self, "_judge_scorer", None)
        if judge_scorer is None:
            judge_scorer_cls = get_scorer(self.metric_name)
            if judge_scorer_cls is None:
                raise ValueError(f"no judge scorer registered for: {self.metric_name}")
            judge_scorer = judge_scorer_cls()
            self._judge_scorer = judge_scorer
        gate_result = self.gate.score(artifact, scenario, metric_config)
        if gate_result.score is not None:
            return gate_result
        if hasattr(judge_scorer, "judge"):
            judge_scorer.judge = self.judge
        return judge_scorer.score(artifact, scenario, metric_config)
