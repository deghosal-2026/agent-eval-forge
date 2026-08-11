"""Deterministic scorer for phantom-step detection.

A phantom step is a tool call that does not advance the agent's state.
This implementation detects phantom steps as consecutive tool calls
to the same tool with the same arguments — a strong signal that the
agent is repeating itself without making progress.
"""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult


@register_scorer
class PhantomStepScorer(Scorer):
    """Score the agent's trajectory for phantom (non-advancing) tool calls.

    Scans consecutive steps in the trajectory. Any step where the tool name
    and arguments match the *immediately preceding* tool-call step is flagged
    as a phantom step.

    Score = 1.0 - (phantom_steps / total_tool_call_steps), clamped to [0, 1].

    * Score is 1.0 when there are zero tool-call steps (no-op pass).
    * Score is 1.0 when no phantom steps are found.
    * Score approaches 0.0 as the phantom ratio approaches 1.0.

    Attributes:
        name: ``"phantom_step_scorer"``
        category: ``"efficiency"``
    """
    name = "phantom_step_scorer"
    category = "efficiency"

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        steps = artifact.trajectory or []

        tool_calls = [s for s in steps if s.type == "tool_call"]
        total = len(tool_calls)

        if total < 2:
            phantom = 0
        else:
            phantom = 0
            for i in range(1, total):
                prev = tool_calls[i - 1]
                curr = tool_calls[i]
                if curr.tool == prev.tool and curr.args == prev.args:
                    phantom += 1

        score = 1.0 - (phantom / total) if total > 0 else 1.0
        score = max(0.0, score)

        threshold = metric_config.get("threshold", 0.7)
        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            category=self.category,
            blocking=False,
            detail={
                "total_tool_calls": total,
                "phantom_steps": phantom,
                "phantom_ratio": round(phantom / total, 4) if total > 0 else 0.0,
            },
            source="deterministic",
            error=None,
        )
