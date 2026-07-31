"""Load and validate scenario packs from YAML or JSON.

Validation is two-stage: a lightweight structural pass (parse errors, required
fields, duplicate ids, known metric names, threshold ranges) that raises
:class:`~evalforge.models.errors.PackParseError` with file/line context, then
a pydantic validation pass that coerces the raw data into the
:class:`~evalforge.models.pack.ScenarioPack` schema. Keeping the structural
checks separate gives users actionable, line-referenced errors instead of a
raw pydantic traceback.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from evalforge.models.errors import PackParseError
from evalforge.models.pack import ScenarioPack

REQUIRED_SCENARIO_FIELDS = ("id", "title", "input")

# Metric names accepted in pack `metrics` blocks. This is the union of:
# 1. The spec's deterministic scorer catalog (§"Deterministic Scorers"):
#    exact_match, schema_valid, field_presence, tool_called, tool_not_called,
#    tool_args_match, step_count, token_count, cost_budget, timeout, tool_sequence
# 2. The spec's LLM-as-judge scorer catalog (§"LLM-as-Judge Scorers"):
#    task_completion, output_correctness, synthesis_quality, clarification_quality,
#    conflict_explanation, hallucination_check, refusal_quality, plan_quality,
#    recovery_quality
# 3. The v0.1 launch pack metric names (spec §"v0.1 Launch Pack — Scenario
#    Definitions"), which are the surface that M2's scoring milestone consumes.
# Packs may only reference metrics in this allowlist; unknown names are rejected
# at load time rather than silently skipped at scoring time.
KNOWN_METRICS = {
    "approval_boundary_adherence",
    "argument_correctness",
    "blast_radius_accuracy",
    "clarification_quality",
    "completeness",
    "conflict_detection",
    "conflict_explanation",
    "contamination_rate",
    "context_isolation",
    "cost_budget",
    "cost_budget_adherence",
    "decomposition_quality",
    "end_to_end_completion",
    "entity_correctness",
    "evidence_grounding",
    "exact_match",
    "extraction_correctness",
    "field_correctness",
    "field_presence",
    "hallucination_check",
    "hallucination_rate",
    "hypothesis_quality",
    "latency",
    "memory_retention",
    "navigation_efficiency",
    "next_step_usefulness",
    "output_correctness",
    "plan_quality",
    "policy_adherence",
    "reasoning_quality",
    "recovery_quality",
    "refusal_quality",
    "relevance",
    "remediation_relevance",
    "retrieval_faithfulness",
    "retry_discipline",
    "runbook_match_accuracy",
    "safety_adherence",
    "schema_valid",
    "schema_validity",
    "scope_adherence",
    "step_count",
    "step_efficiency",
    "subtask_boundary_adherence",
    "synthesis_quality",
    "task_completion",
    "timeout",
    "token_count",
    "tool_args_match",
    "tool_called",
    "tool_correctness",
    "tool_not_called",
    "tool_sequence",
    "trajectory_consistency",
    "uncertainty_handling",
    "unsafe_action_avoidance",
    "verification_completeness",
    "verification_quality",
    "zero_disallowed_actions",
    "zero_unauthorized_actions",
}


def load_pack(path: str | Path) -> ScenarioPack:
    """Parse and validate a scenario pack from a YAML or JSON file."""
    path = Path(path)
    if not path.exists():
        raise PackParseError(f"pack file not found: {path}", file=str(path))
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PackParseError(f"could not read pack: {exc}", file=str(path)) from exc

    if path.suffix.lower() == ".json":
        data = _parse_json(raw, path)
    else:
        data = _parse_yaml(raw, path)

    _validate(data, path)
    try:
        return ScenarioPack.model_validate(data)
    except ValidationError as exc:
        raise PackParseError(f"invalid pack structure: {exc}", file=str(path)) from exc


def _parse_yaml(raw: str, path: Path) -> object:
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark is not None else None
        raise PackParseError(f"malformed YAML: {exc}", file=str(path), line=line) from exc


def _parse_json(raw: str, path: Path) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PackParseError(f"malformed JSON: {exc.msg}", file=str(path), line=exc.lineno) from exc


def _validate(data: object, path: Path) -> None:
    """Run structural checks that give better errors than pydantic's."""
    if not isinstance(data, dict):
        raise PackParseError("pack must be a mapping with `pack` and `scenarios`", file=str(path))
    pack = data.get("pack")
    if not isinstance(pack, dict):
        raise PackParseError("missing required `pack` metadata block", file=str(path))
    for field in ("name", "version"):
        if field not in pack:
            raise PackParseError(f"pack metadata missing required field: {field}", file=str(path))

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        raise PackParseError("missing required `scenarios` list", file=str(path))

    seen: set[str] = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise PackParseError(f"scenario {index} must be a mapping", file=str(path))
        for field in REQUIRED_SCENARIO_FIELDS:
            if field not in scenario:
                raise PackParseError(
                    f"scenario {index} missing required field: {field}",
                    file=str(path),
                )
        sid = scenario["id"]
        if sid in seen:
            raise PackParseError(f"duplicate scenario id: {sid}", file=str(path))
        seen.add(sid)

        metrics = scenario.get("metrics", {})
        if not isinstance(metrics, dict):
            raise PackParseError(f"scenario {sid} metrics must be a mapping", file=str(path))
        for name, metric in metrics.items():
            if name not in KNOWN_METRICS:
                raise PackParseError(f"scenario {sid} uses unknown metric: {name}", file=str(path))
            if not isinstance(metric, dict):
                msg = f"scenario {sid} metric {name} must be a mapping"
                raise PackParseError(msg, file=str(path))
            threshold = metric.get("threshold")
            if threshold is not None:
                if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
                    raise PackParseError(
                        f"scenario {sid} metric {name} threshold must be a number: {threshold!r}",
                        file=str(path),
                    )
                if not (0.0 <= threshold <= 1.0):
                    raise PackParseError(
                        f"scenario {sid} metric {name} threshold out of range: {threshold}",
                        file=str(path),
                    )
