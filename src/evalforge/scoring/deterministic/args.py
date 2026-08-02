"""Deterministic scorer for tool-argument correctness.

Scores how precisely an agent's tool calls match the arguments the scenario
declares as required. Two expectation forms are supported:

- ``expected.tool`` + ``expected.args`` (classic form): every call to the
  expected tool must pass exactly the expected arguments.
- ``expected.trace`` + ``args_match`` (launch-pack form): the ordered
  sequence of required tool steps, each declaring its args and a match mode,
  ``exact`` or ``subset``. ``subset`` lets the agent supply extra, harmless
  arguments on top of the required ones (e.g. a region the scenario doesn't
  constrain).

The score is the fraction of declared expectations that at least one tool
call satisfies (a trace entry with no ``args`` is satisfied by any call to
its tool). When the scenario declares no argument expectation at all, the
scorer is a no-op that always passes so it can't drag unrelated scenarios
down.
"""

from __future__ import annotations

from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Expected, Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult

# (tool_name, expected_args_or_None, match_mode)
Expectation = tuple[str, dict[str, Any] | None, str]


def _extract_expectations(expected: Expected | None) -> list[Expectation]:
    """Extract a list of ``(tool, args, match_mode)`` expectations.

    Handles both the ``tool_args`` form (``expected.tool`` + ``expected.args``)
    and the launch-pack ``tool_trace`` form (one expectation per ``trace``
    entry with ``args_match``). Returns ``match_mode`` in {"exact", "subset"}.
    An empty list signals the caller to short-circuit to a passing score.

    Args:
        expected: The scenario's expected declaration, or None.

    Returns:
        List of (tool_name, args_dict_or_None, match_mode) tuples. Empty if
        no argument expectations are declared.
    """
    if expected is None:
        return []
    if expected.trace and isinstance(expected.trace, list):
        out: list[tuple[str, dict[str, Any] | None, str]] = []
        for entry in expected.trace:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool", "")
            args = entry.get("args")
            mode = entry.get("args_match", "exact")
            out.append((tool, args if isinstance(args, dict) else None, mode))
        return out
    tool = expected.tool or ""
    args = expected.args
    return [(tool, args if isinstance(args, dict) else None, "exact")]


def _args_match(call_args: dict[str, Any], exp_args: dict[str, Any], mode: str) -> bool:
    """Check whether a tool call's args satisfy the expectation.

    - ``exact``: the call args must equal the expected args (dict equality).
    - ``subset``: the expected args must be present in the call args (the agent
      may supply extra args beyond the required ones). Dict item comparison
      via ``items() <=`` treats each expected key/value pair independently.

    Args:
        call_args: The actual arguments the agent passed to the tool.
        exp_args: The arguments the scenario requires.
        mode: ``"exact"`` or ``"subset"``.

    Returns:
        True if the call args satisfy the expectation.
    """
    if mode == "subset":
        return exp_args.items() <= call_args.items()
    return call_args == exp_args


def _satisfied(
    trajectory: list[Any] | None,
    exp_tool: str,
    exp_args: dict[str, Any] | None,
    mode: str,
) -> bool:
    """Whether any tool_call satisfies a single expectation.

    A call satisfies the expectation when it targets the expected tool (when
    named) and its args match. An expectation with no ``args`` declares no
    argument constraint, so any call to the tool satisfies it.

    Args:
        trajectory: The agent's trajectory steps.
        exp_tool: The expected tool name (empty string means any tool).
        exp_args: Expected arguments, or None if no argument constraint.
        mode: Match mode (``"exact"`` or ``"subset"``).

    Returns:
        True if at least one tool call in the trajectory satisfies the expectation.
    """
    for step in trajectory or []:
        if getattr(step, "type", "") != "tool_call":
            continue
        if exp_tool and step.tool != exp_tool:
            continue
        call_args = step.args if isinstance(step.args, dict) else {}
        if exp_args is None:
            return True
        if _args_match(call_args, exp_args, mode):
            return True
    return False


@register_scorer
class ArgumentCorrectnessScorer(Scorer):
    """Score the fraction of argument expectations satisfied by the trajectory.

    For each expected tool+args pair (declared via ``expected.trace`` or
    ``expected.tool`` + ``expected.args``), checks whether at least one tool
    call in the trajectory satisfies it. The score is matched / total expectations.
    When no argument expectations are declared, the scorer is a no-op (always
    passes with score 1.0).

    Attributes:
        name: ``"argument_correctness"``
        category: ``"correctness"``
    """
    name = "argument_correctness"
    category = "correctness"

    def score(
        self, artifact: RunArtifact, scenario: Scenario, metric_config: dict[str, Any]
    ) -> ScoreResult:
        expectations = _extract_expectations(scenario.expected)
        if not expectations:
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
        matched = sum(
            1
            for exp_tool, exp_args, mode in expectations
            if _satisfied(artifact.trajectory, exp_tool, exp_args, mode)
        )
        # Fraction of declared expectations the trajectory satisfies. Any
        # unmet expectation (wrong args, wrong tool, or a required call never
        # made) correctly fails the scenario.
        score = matched / len(expectations)
        threshold = metric_config.get("threshold", 1.0)
        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            category=self.category,
            blocking=False,
            detail={"expected_expectations": len(expectations), "matched": matched},
            source="deterministic",
            error=None,
        )
