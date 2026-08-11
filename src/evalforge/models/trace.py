"""Execution trace model for adapter-agent boundary diagnostics.

Tracks where an agent's actual execution diverged from the expected execution
path, producing structured :attr:`~RunArtifact.trace_diff` data that makes
silent failures actionable.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DIVERGENCE_TYPES = Literal[
    "stopped_early",
    "skipped_step",
    "hung",
    "errored",
    "silent_empty",
]

EXPECTED_STEPS_DEFAULT: list[str] = [
    "tool_dispatch",
    "model_call",
    "structured_output",
    "completion",
]


class ExecutionTrace(BaseModel):
    """Model capturing the divergence between expected and actual execution.

    Attributes:
        expected_steps: The canonical execution path the agent should follow.
        actual_steps: The steps the agent actually took (derived from trajectory,
            adapter diagnostics, or process exit information).
        divergence_point: The step at which execution diverged, if any.
        divergence_type: The kind of divergence observed, if any.
    """

    expected_steps: list[str] = Field(default_factory=lambda: list(EXPECTED_STEPS_DEFAULT))
    actual_steps: list[str] = Field(default_factory=list)
    divergence_point: str | None = None
    divergence_type: DIVERGENCE_TYPES | None = None


def compute_trace_diff(
    artifact_has_trajectory: bool,
    artifact_status: str,
    trajectory_len: int = 0,
) -> dict[str, Any] | None:
    """Compute a trace-diff dict from artifact-level signals.

    Args:
        artifact_has_trajectory: Whether the artifact has any trajectory steps.
        artifact_status: The terminal status of the artifact (``"completed"``,
            ``"error"``, ``"timeout"``, ``"aborted"``).
        trajectory_len: Number of trajectory steps (used to estimate how far the
            agent got).

    Returns:
        A dict with keys ``divergence_type``, ``divergence_point``,
        ``expected_steps``, ``actual_steps``, or ``None`` when no divergence
        is detected (i.e. status is ``"completed"`` and trajectory exists).

    Note:
        The heuristic is intentionally conservative: a completed artifact with
        a non-empty trajectory is assumed to have executed normally. Only error,
        timeout, and aborted artifacts get a trace diff, and the divergence
        type is inferred from the trajectory emptiness and the status.
    """
    if artifact_status == "completed" and artifact_has_trajectory:
        return None

    expected = list(EXPECTED_STEPS_DEFAULT)
    actual: list[str] = []

    if artifact_status == "timeout":
        point = expected[trajectory_len] if trajectory_len < len(expected) else "unknown"
        return {
            "divergence_type": "stopped_early",
            "divergence_point": point,
            "expected_steps": expected,
            "actual_steps": actual,
        }

    if artifact_status == "error":
        if not artifact_has_trajectory:
            return {
                "divergence_type": "silent_empty",
                "divergence_point": expected[0],
                "expected_steps": expected,
                "actual_steps": actual,
            }
        point = expected[trajectory_len] if trajectory_len < len(expected) else "unknown"
        return {
            "divergence_type": "errored",
            "divergence_point": point,
            "expected_steps": expected,
            "actual_steps": actual,
        }

    return None
