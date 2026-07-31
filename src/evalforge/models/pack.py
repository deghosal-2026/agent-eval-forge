"""Pydantic models for scenario packs.

A scenario pack is the unit of evaluation configuration: pack metadata plus a
list of scenarios. Each scenario describes the input handed to an agent, the
tool surface it may touch, what "correct" looks like, and how the run is
scored. These models are the schema against which pack YAML/JSON is validated
(see :mod:`evalforge.loading.pack_loader`).

Ground-truth discipline: ``expected`` and ``metrics`` are evaluation-only and
must never be transmitted to an agent — they live here for scoring but are
stripped when building invocation payloads (see
:func:`evalforge.adapters.base.build_invocation_payload`).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Tool(BaseModel):
    """A tool an agent may call.

    Tools are identified by ``name``; ``description`` is optional and is what
    an LLM agent uses to decide when to call it.
    """

    name: str
    description: str | None = None


class Expected(BaseModel):
    """Expected agent behavior for a scenario.

    The ``type`` determines which field carries the expectation:

    - ``exact``: ``value`` is the literal final answer string.
    - ``schema``: ``schema`` is a JSON schema the final output must satisfy.
    - ``tool_trace``: ``trace`` is the ordered sequence of tool calls expected.
    - ``rubric``: ``criteria`` is a list of qualitative pass/fail statements.
    """

    type: Literal["exact", "schema", "tool_trace", "rubric"]
    value: str | None = None
    # Shadowing BaseModel.schema() is intentional: the pack format uses the
    # key `schema`, and pydantic v2 tolerates it; silence mypy's complaint.
    schema: dict[str, Any] | None = None  # type: ignore[assignment]
    required_fields: list[str] | None = None
    trace: list[dict[str, Any]] | None = None
    criteria: list[str] | None = None


class Metric(BaseModel):
    """Scoring metric configuration.

    ``weight`` scales the metric's contribution to an aggregate score;
    ``threshold`` is the pass/fail cutoff in ``[0, 1]`` (checked at load time).
    """

    weight: float = 1.0
    threshold: float | None = None


class Budget(BaseModel):
    """Resource budget for a scenario.

    Any field may be ``None`` to mean "unbounded". Enforced by adapters where
    applicable; recorded on artifacts for auditability.
    """

    max_steps: int | None = None
    max_tokens: int | None = None
    max_cost_usd: float | None = None


class Scenario(BaseModel):
    """A single evaluation scenario.

    ``input`` is the prompt/task handed to the agent. ``context`` carries
    ambient state (facts, environment, docs) the agent may reason about.
    ``expected``/``metrics`` are evaluation-only and never sent to agents.
    """

    id: str
    title: str
    goal: str | None = None
    input: str
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[Tool] = Field(default_factory=list)
    disallowed_tools: list[Tool] = Field(default_factory=list)
    expected: Expected | None = None
    metrics: dict[str, Metric] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    budget: Budget | None = None


class PackMetadata(BaseModel):
    """Scenario pack metadata."""

    name: str
    version: str
    description: str | None = None
    min_evalforge: str | None = None


class ScenarioPack(BaseModel):
    """A parsed scenario pack: metadata + scenarios."""

    pack: PackMetadata
    scenarios: list[Scenario]
