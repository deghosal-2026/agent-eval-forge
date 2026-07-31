"""Deterministic scorer for tool-argument correctness."""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult


@register_scorer
class ArgumentCorrectnessScorer(Scorer):
    name = "argument_correctness"
    category = "correctness"

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        expected = scenario.expected
        if expected is None or expected.args is None:
            return ScoreResult(
                metric=self.name,
                score=1.0,
                threshold=1.0,
                passed=True,
                category=self.category,
                blocking=False,
                detail={},
                source="deterministic",
                error=None,
            )
        exp_args = expected.args
        exp_tool = expected.tool or ""
        matches = 0
        total = 0
        for step in artifact.trajectory or []:
            if getattr(step, "type", "") != "tool_call":
                continue
            if exp_tool and step.tool != exp_tool:
                continue
            total += 1
            call_args = step.args if isinstance(step.args, dict) else {}
            if call_args == exp_args:
                matches += 1
            elif isinstance(exp_args, dict) and call_args.items() <= exp_args.items():
                matches += 1  # subset match
        score = matches / total if total else 1.0
        threshold = metric_config.get("threshold", 1.0)
        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            category=self.category,
            blocking=False,
            detail={"expected_args": exp_args, "expected_tool": exp_tool},
            source="deterministic",
            error=None,
        )
