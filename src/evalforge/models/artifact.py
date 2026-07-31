"""Pydantic models for run artifacts.

A :class:`RunArtifact` is the normalized, persisted result of running one
scenario against an agent — the unit that scoring (M2) consumes. It carries
the final output, the trajectory of steps the agent took, cost accounting, and
a terminal status. The model round-trips losslessly through JSON so artifacts
written to ``.evalforge/runs/<run_id>/artifacts/*.json`` can be re-loaded
identically (spec §"Run Artifact").
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TrajectoryStep(BaseModel):
    """One step in an agent trajectory.

    The ``type`` determines which fields are expected (spec §"TrajectoryStep"):

    - ``tool_call``: ``tool`` + ``args``
    - ``tool_result``: ``tool`` + ``result``
    - ``response``: ``content``
    - ``note``: ``content`` (agent reasoning, optional)

    Extra fields are tolerated at validation time for forward compatibility.
    """

    type: Literal["tool_call", "tool_result", "response", "note"]
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: Any | None = None
    content: str | None = None
    duration_ms: int | None = None
    error: str | None = None


class Cost(BaseModel):
    """Token and dollar cost of a run.

    ``total_tokens`` is tracked explicitly rather than derived so adapters can
    report provider totals directly.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class RunOutput(BaseModel):
    """Final agent output.

    ``final`` is the human-readable final answer; ``structured`` is the
    machine-readable form (parsed JSON, tool result tree, etc.) when present.
    """

    final: str | None = None
    structured: Any = None


class RunTimestamps(BaseModel):
    """Run timing (ISO-8601 UTC start/end plus wall-clock duration)."""

    start: str
    end: str
    duration_ms: int


class RunArtifact(BaseModel):
    """Normalized result of running one scenario against an agent."""

    id: str
    scenario_id: str
    agent: dict[str, Any] = Field(default_factory=dict)
    timestamp: RunTimestamps
    output: RunOutput = Field(default_factory=RunOutput)
    trajectory: list[TrajectoryStep] = Field(default_factory=list)
    cost: Cost = Field(default_factory=Cost)
    status: Literal["completed", "timeout", "error", "aborted"] = "completed"
    error: str | None = None
