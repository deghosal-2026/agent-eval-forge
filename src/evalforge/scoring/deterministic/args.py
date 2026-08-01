"""Deterministic scorer for tool-argument correctness.

Scores how precisely an agent's tool calls match the arguments the scenario
declares as required. Two expectation forms are supported:

- ``expected.tool`` + ``expected.args`` (classic form): every call to the
  expected tool must pass exactly the expected arguments.
- ``expected.trace[0]`` + ``args_match`` (launch-pack form): the first
  required tool step declares its args and a match mode, ``exact`` or
  ``subset``. ``subset`` lets the agent supply extra, harmless arguments on
  top of the required ones (e.g. a region the scenario doesn't constrain).

The score is the fraction of matching calls over the total calls made to the
expected tool. When the scenario declares no argument expectation at all, the
scorer is a no-op that always passes so it can't drag unrelated scenarios down.
"""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Expected, Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult


def _extract_expectation(expected: Expected | None) -> tuple[str, dict[str, Any] | None, str]:
    """Extract (tool, args, match_mode) from an ``Expected`` block.

    Handles both the ``tool_args`` form (``expected.tool`` + ``expected.args``)
    and the launch-pack ``tool_trace`` form (``expected.trace[0]`` with
    ``args_match``). Returns ``match_mode`` in {"exact", "subset"}.

    Returns an empty tool and ``None`` args when no argument expectation
    exists, signalling the caller to short-circuit to a passing score.
    """
    if expected is None:
        return "", None, "exact"
    if expected.trace and isinstance(expected.trace, list):
        # Launch-pack form: the first expected tool step drives the check.
        first = expected.trace[0]
        tool = first.get("tool", "") if isinstance(first, dict) else ""
        args = first.get("args") if isinstance(first, dict) else None
        mode = first.get("args_match", "exact") if isinstance(first, dict) else "exact"
        return tool, args if isinstance(args, dict) else None, mode
    tool = expected.tool or ""
    args = expected.args
    return tool, args if isinstance(args, dict) else None, "exact"


def _args_match(call_args: dict[str, Any], exp_args: dict[str, Any], mode: str) -> bool:
    """Check whether a tool call's args satisfy the expectation.

    - ``exact``: the call args must equal the expected args (dict equality).
    - ``subset``: the expected args must be present in the call args (the agent
      may supply extra args beyond the required ones). Dict item comparison
      via ``items() <=`` treats each expected key/value pair independently.
    """
    if mode == "subset":
        return exp_args.items() <= call_args.items()
    return call_args == exp_args


@register_scorer
class ArgumentCorrectnessScorer(Scorer):
    name = "argument_correctness"
    category = "correctness"

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        expected = scenario.expected
        exp_tool, exp_args, match_mode = _extract_expectation(expected)
        if exp_args is None:
            # No argument expectation declared: nothing to verify, so pass.
            # This keeps the metric inert for scenarios that only gate on
            # tool choice or output shape.
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
        matches = 0
        total = 0
        for step in artifact.trajectory or []:
            # Only tool_call steps can carry arguments; ignore responses,
            # tool results, and any future step kinds.
            if getattr(step, "type", "") != "tool_call":
                continue
            # When the expectation names a tool, calls to other tools don't
            # count against the argument score (tool choice is scored by
            # tool_correctness instead).
            if exp_tool and step.tool != exp_tool:
                continue
            total += 1
            call_args = step.args if isinstance(step.args, dict) else {}
            if _args_match(call_args, exp_args, match_mode):
                matches += 1
        # Fraction of expected-tool calls whose args satisfy the expectation.
        # Zero calls to the expected tool yields 0.0, correctly failing the
        # scenario when the agent never made the required call.
        score = matches / total if total else 0.0
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
