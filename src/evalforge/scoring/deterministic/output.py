"""Deterministic scorers for output-format metrics."""

from __future__ import annotations

import json
from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult


@register_scorer
class SchemaValidityScorer(Scorer):
    name = "schema_validity"
    category = "correctness"

    def score(self, artifact: RunArtifact, scenario: Scenario,
              metric_config: dict[str, Any]) -> ScoreResult:
        expected = scenario.expected
        if expected is None or expected.schema is None:
            return ScoreResult(metric=self.name, score=1.0, threshold=1.0,
                               passed=True, category=self.category, blocking=False,
                               detail={}, source="deterministic", error=None)
        output = artifact.output.final or ""
        required_keys = expected.schema if isinstance(expected.schema, dict) else {}
        try:
            parsed = json.loads(output) if isinstance(output, str) else output
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        found = sum(1 for k in required_keys if k in parsed) if isinstance(parsed, dict) else 0
        total = len(required_keys) or 1
        score = found / total
        threshold = metric_config.get("threshold", 1.0)
        return ScoreResult(
            metric=self.name, score=score, threshold=threshold,
            passed=score >= threshold, category=self.category, blocking=False,
            detail={"required": list(required_keys), "found": list(
                k for k in required_keys if isinstance(parsed, dict) and k in parsed
            )}, source="deterministic", error=None,
        )


@register_scorer
class FieldCorrectnessScorer(Scorer):
    name = "field_correctness"
    category = "correctness"

    def score(self, artifact: RunArtifact, scenario: Scenario,
              metric_config: dict[str, Any]) -> ScoreResult:
        expected = scenario.expected
        if expected is None or expected.schema is None:
            return ScoreResult(metric=self.name, score=1.0, threshold=1.0,
                               passed=True, category=self.category, blocking=False,
                               detail={}, source="deterministic", error=None)
        required_keys = expected.schema if isinstance(expected.schema, dict) else {}
        output = artifact.output.structured or artifact.output.final or ""
        parsed = output if isinstance(output, dict) else {}
        found = sum(1 for k in required_keys if k in parsed)
        total = len(required_keys) or 1
        score = found / total
        threshold = metric_config.get("threshold", 1.0)
        return ScoreResult(
            metric=self.name, score=score, threshold=threshold,
            passed=score >= threshold, category=self.category, blocking=False,
            detail={"required": list(required_keys), "found": list(
                k for k in required_keys if k in parsed
            )}, source="deterministic", error=None,
        )
