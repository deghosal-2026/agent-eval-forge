"""Adapter contract and shared helpers.

Every adapter follows the same contract: given a
:class:`~evalforge.models.pack.Scenario` and a config dict, invoke the agent
and return a normalized :class:`~evalforge.models.artifact.RunArtifact`. This
module owns the three shared pieces of that pipeline:

1. :func:`build_invocation_payload` — the restricted payload sent to agents.
   Evaluation-only fields (``expected``, ``metrics``) are **never** included
   (spec §"Agent Invocation Payload"); this is the ground-truth-leakage
   guarantee.
2. :func:`parse_agent_stdout` — parses the agent's stdout as a JSON envelope
   (``evalforge.run_envelope.v1``) with a raw-text fallback unless
   ``strict_output`` is set.
3. :class:`Adapter` — the abstract base that turns an invocation result into a
   ``RunArtifact``, capturing timing, cost, trajectory, and error/status
   normalization so concrete adapters only implement ``_invoke``.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps, TrajectoryStep
from evalforge.models.errors import AdapterError, AgentTimeoutError
from evalforge.models.pack import Scenario

INVOCATION_SCHEMA_VERSION = "evalforge.invocation_payload.v1"
RUN_ENVELOPE_SCHEMA_VERSION = "evalforge.run_envelope.v1"


def build_invocation_payload(scenario: Scenario, run_id: str) -> dict[str, Any]:
    """Build the restricted payload sent to an agent.

    Evaluation-only fields (``expected``, ``metrics``) are never included, so
    agents cannot game or memorize ground truth. Tools are sent as ``ToolSpec``
    objects (name + description), not bare strings, per the spec.
    """
    return {
        "schema_version": INVOCATION_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": scenario.id,
        "input": scenario.input,
        "context": scenario.context,
        "allowed_tools": [tool.model_dump() for tool in scenario.allowed_tools],
        "disallowed_tools": [tool.model_dump() for tool in scenario.disallowed_tools],
        "budget": scenario.budget.model_dump() if scenario.budget else {},
    }


def parse_agent_stdout(stdout: str, *, strict: bool = False) -> dict[str, Any]:
    """Parse agent stdout as a JSON envelope, falling back to raw text.

    When ``strict`` is true, non-JSON output raises
    :class:`~evalforge.models.errors.AdapterError` instead of being treated as
    a plain-text final answer.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        if strict:
            raise AdapterError("agent stdout is not valid JSON (strict_output=true)") from None
        return _raw_text_envelope(stdout)
    if not isinstance(data, dict):
        if strict:
            raise AdapterError("agent stdout is not a JSON object (strict_output=true)") from None
        return _raw_text_envelope(stdout)
    return data


def _raw_text_envelope(stdout: str) -> dict[str, Any]:
    """Build a run envelope from plain text, stripping terminal whitespace."""
    return {
        "schema_version": RUN_ENVELOPE_SCHEMA_VERSION,
        "status": "completed",
        "output": {"final": stdout.rstrip(), "structured": None},
        "trajectory": {"steps": []},
        "cost": None,
        "error": None,
    }


class Adapter(ABC):
    """Base class for agent adapters.

    Subclasses implement :meth:`_invoke`, which performs the actual agent
    invocation and returns either raw stdout (``str``) or an already-parsed
    envelope (``dict``). :meth:`run` handles payload building, timing,
    error/status normalization, and artifact construction.
    """

    name: str

    def run(self, scenario: Scenario, config: dict[str, Any]) -> RunArtifact:
        """Invoke the agent for a scenario and return a normalized RunArtifact."""
        run_id = config.get("run_id", "run-unknown")
        payload = build_invocation_payload(scenario, run_id)
        start_iso = _now_iso()
        start_ms = _now_ms()
        strict = bool(config.get("strict_output", False))
        try:
            raw = self._invoke(payload, config)
            if isinstance(raw, str):
                envelope = parse_agent_stdout(raw, strict=strict)
            elif isinstance(raw, dict):
                envelope = raw
            else:
                raise AdapterError(f"adapter returned unexpected type: {type(raw).__name__}")
        except AgentTimeoutError as exc:
            return _artifact_for_error(
                scenario, run_id, "timeout", str(exc), config, start_iso, start_ms
            )
        except AdapterError as exc:
            return _artifact_for_error(
                scenario, run_id, "error", str(exc), config, start_iso, start_ms
            )
        except Exception as exc:  # normalize unexpected agent failures
            return _artifact_for_error(
                scenario, run_id, "error", str(exc), config, start_iso, start_ms
            )

        return _artifact_from_envelope(envelope, scenario, run_id, config, start_iso, start_ms)

    @abstractmethod
    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str | dict[str, Any]:
        """Invoke the agent; return raw stdout (str) or an envelope dict."""


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _artifact_for_error(
    scenario: Scenario,
    run_id: str,
    status: str,
    error: str,
    config: dict[str, Any],
    start_iso: str,
    start_ms: int,
) -> RunArtifact:
    end_ms = _now_ms()
    return RunArtifact(
        id=f"{run_id}-{scenario.id}",
        scenario_id=scenario.id,
        agent=_sanitize_agent(config),
        timestamp=RunTimestamps(start=start_iso, end=_now_iso(), duration_ms=end_ms - start_ms),
        output=RunOutput(final=None, structured=None),
        trajectory=[],
        cost=Cost(),
        status=status,  # type: ignore[arg-type]
        error=error,
    )


def _artifact_from_envelope(
    envelope: dict[str, Any],
    scenario: Scenario,
    run_id: str,
    config: dict[str, Any],
    start_iso: str,
    start_ms: int,
) -> RunArtifact:
    end_ms = _now_ms()
    status = envelope.get("status", "completed")
    output = envelope.get("output") or {}
    trajectory_raw = (envelope.get("trajectory") or {}).get("steps") or []
    cost_raw = envelope.get("cost")
    steps: list[TrajectoryStep] = []
    for step in trajectory_raw:
        parsed = _step_or_skip(step)
        if parsed is not None:
            steps.append(parsed)

    return RunArtifact(
        id=f"{run_id}-{scenario.id}",
        scenario_id=scenario.id,
        agent=_sanitize_agent(config),
        timestamp=RunTimestamps(start=start_iso, end=_now_iso(), duration_ms=end_ms - start_ms),
        output=RunOutput(final=output.get("final"), structured=output.get("structured")),
        trajectory=steps,
        cost=Cost.model_validate(cost_raw) if isinstance(cost_raw, dict) else Cost(),
        status=status,
        error=envelope.get("error"),
    )


def _step_or_skip(step: Any) -> TrajectoryStep | None:
    """Coerce a raw trajectory step into a model, skipping malformed ones."""
    if not isinstance(step, dict):
        return None
    try:
        return TrajectoryStep.model_validate(step)
    except Exception:  # a malformed step should not fail the run
        return None


def _sanitize_agent(config: dict[str, Any]) -> dict[str, Any]:
    """Copy config minus any secret-looking keys, for artifact provenance.

    Agent config is written into the run index and artifacts; API keys and
    tokens must never be persisted (spec §"Run Index").
    """
    secret_keys = {"api_key", "token", "secret", "password"}
    return {
        key: value
        for key, value in config.items()
        if key not in secret_keys
    }
