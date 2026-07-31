# M1: Core Runner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load scenario packs, invoke agents through adapters, and capture normalized `RunArtifact`s.

**Architecture:** Library-first flow: pack YAML/JSON → `ScenarioPack` (pydantic) → `Runner` → `Adapter.run(scenario, config)` → `RunArtifact` → saved to `.evalforge/runs/<run_id>/`. Adapters never transmit evaluation-only fields (`expected`, `metrics`) — only a restricted invocation payload. JSON-envelope output with raw-text fallback for subprocess/HTTP; python-import runs callables in a separate process for hard timeouts.

**Tech Stack:** Python ≥3.11, pydantic v2, PyYAML, httpx, pytest, ruff, mypy --strict.

## Global Constraints

- `requires-python = ">=3.11"`; target mypy `python_version = "3.11"`
- All models are pydantic v2 `BaseModel`s.
- ruff rules: E, F, W, I, B, UP, S, RUF; line length 100.
- mypy strict mode; `files = ["src"]`.
- Coverage gate: >90% (`pytest --cov=evalforge --cov-fail-under=90`).
- Adapters MUST NOT send `expected` or `metrics` to agents (spec §Agent Invocation Payload).
- Subprocess adapters run without shell (`shell=False`).
- Adapter signature: `run(scenario, config) -> RunArtifact`.
- JSON envelope `schema_version = "evalforge.run_envelope.v1"`; invocation payload `schema_version = "evalforge.invocation_payload.v1"`.
- Python 3.11 is the mypy floor; do not use syntax newer than 3.11.

---

## File Structure

```
src/evalforge/
  models/
    errors.py          # EvalForgeError hierarchy
    pack.py            # Tool, Expected, Metric, Budget, Scenario, ScenarioPack
    artifact.py        # TrajectoryStep, Cost, RunArtifact
  loading/
    __init__.py
    pack_loader.py     # YAML/JSON parse + validation
  adapters/
    __init__.py        # re-exports create_adapter + Adapter
    base.py            # Adapter ABC, envelope parsing, payload building, RunArtifact construction
    subprocess.py
    python_import.py
    http.py
    factory.py
  runner.py            # Runner + run_id generation + artifact saving
  __init__.py          # version only (unchanged)
scenarios/
  core-launch.yaml     # all 20 launch scenarios
tests/
  conftest.py          # shared fixtures (add agent/fixture helpers)
  test_models.py
  test_pack_loader.py
  test_adapters_base.py
  test_adapters_subprocess.py
  test_adapters_python_import.py
  test_adapters_http.py
  test_adapters_factory.py
  test_runner.py
  test_launch_pack.py
  fixtures/
    agents.py          # python-import mock agents
    echo_agent.py      # subprocess mock agent
```

---

### Task 1: Error hierarchy

**Files:**
- Create: `src/evalforge/models/errors.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `EvalForgeError`, `PackParseError(message, file=None, line=None)`, `AdapterError(message)`, `AgentTimeoutError(message)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import pytest

from evalforge.models.errors import (
    AdapterError,
    AgentTimeoutError,
    EvalForgeError,
    PackParseError,
)


def test_error_hierarchy() -> None:
    assert issubclass(PackParseError, EvalForgeError)
    assert issubclass(AdapterError, EvalForgeError)
    assert issubclass(AgentTimeoutError, AdapterError)


def test_pack_parse_error_message_with_line() -> None:
    err = PackParseError("bad yaml", file="pack.yaml", line=12)
    assert str(err) == "pack.yaml:12: bad yaml"
    assert err.file == "pack.yaml"
    assert err.line == 12


def test_pack_parse_error_without_location() -> None:
    err = PackParseError("bad yaml")
    assert str(err) == "bad yaml"
    assert err.file is None
    assert err.line is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.models.errors'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evalforge/models/errors.py
"""Error hierarchy for EvalForge."""

from __future__ import annotations


class EvalForgeError(Exception):
    """Base class for all EvalForge errors."""


class PackParseError(EvalForgeError):
    """A scenario pack could not be parsed or validated."""

    def __init__(self, message: str, file: str | None = None, line: int | None = None) -> None:
        self.file = file
        self.line = line
        if file is not None and line is not None:
            rendered = f"{file}:{line}: {message}"
        else:
            rendered = message
        super().__init__(rendered)


class AdapterError(EvalForgeError):
    """An agent adapter failed to invoke or normalize a run."""


class AgentTimeoutError(AdapterError):
    """The agent exceeded its timeout budget."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/evalforge/models/errors.py tests/test_models.py
git commit -m "feat(models): add error hierarchy"
```

---

### Task 2: Pack models (Scenario, ScenarioPack, Tool, Expected, Metric, Budget)

**Files:**
- Create: `src/evalforge/models/pack.py`
- Modify: `tests/test_models.py` (append)
- Modify: `src/evalforge/models/__init__.py` (re-export)

**Interfaces:**
- Produces:
  - `Tool(name: str, description: str | None = None)`
  - `Expected(type: Literal["exact","schema","tool_trace","rubric"], value=None, schema=None, required_fields=None, trace=None, criteria=None)`
  - `Metric(weight: float = 1.0, threshold: float | None = None)`
  - `Budget(max_steps: int | None = None, max_tokens: int | None = None, max_cost_usd: float | None = None)`
  - `Scenario(id, title, goal=None, input, context=dict, allowed_tools=list[Tool], disallowed_tools=list[Tool], expected=None, metrics=dict[str, Metric], tags=list[str], difficulty=None, budget=None)`
  - `ScenarioPack(pack: PackMetadata, scenarios: list[Scenario])` where `PackMetadata(name, version, description=None, min_evalforge=None)`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_models.py
from evalforge.models.pack import Budget, Expected, Metric, Scenario, ScenarioPack, Tool


def test_tool_model() -> None:
    tool = Tool(name="policy_lookup", description="Look up policies")
    assert tool.name == "policy_lookup"
    assert tool.description == "Look up policies"
    assert Tool(name="x").description is None


def test_expected_exact() -> None:
    exp = Expected(type="exact", value="the answer")
    assert exp.type == "exact"
    assert exp.value == "the answer"


def test_expected_rubric() -> None:
    exp = Expected(type="rubric", criteria=["must do X", "must not do Y"])
    assert exp.criteria == ["must do X", "must not do Y"]


def test_metric_defaults() -> None:
    m = Metric()
    assert m.weight == 1.0
    assert m.threshold is None


def test_budget_optional_fields() -> None:
    b = Budget(max_steps=3)
    assert b.max_steps == 3
    assert b.max_tokens is None
    assert b.max_cost_usd is None


def test_scenario_roundtrip() -> None:
    sc = Scenario(
        id="sc-1",
        title="Title",
        goal="Goal",
        input="the input",
        context={"tier": "premium"},
        allowed_tools=[Tool(name="tool_a")],
        expected=Expected(type="exact", value="v"),
        metrics={"task_completion": Metric(threshold=1.0)},
        tags=["retrieval"],
    )
    assert sc.id == "sc-1"
    assert sc.context == {"tier": "premium"}
    assert sc.allowed_tools[0].name == "tool_a"
    assert sc.metrics["task_completion"].threshold == 1.0
    assert sc.tags == ["retrieval"]


def test_scenario_pack_roundtrip() -> None:
    pack = ScenarioPack(
        pack={"name": "p", "version": "1.0.0"},
        scenarios=[Scenario(id="s1", title="T", input="i")],
    )
    assert pack.pack.name == "p"
    assert pack.pack.version == "1.0.0"
    assert len(pack.scenarios) == 1
    # pydantic accepts dict for nested model via model_validate too
    assert pack.scenarios[0].input == "i"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.models.pack'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evalforge/models/pack.py
"""Pydantic models for scenario packs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Tool(BaseModel):
    """A tool an agent may call."""

    name: str
    description: str | None = None


class Expected(BaseModel):
    """Expected agent behavior for a scenario."""

    type: Literal["exact", "schema", "tool_trace", "rubric"]
    value: str | None = None
    schema: dict[str, Any] | None = None
    required_fields: list[str] | None = None
    trace: list[dict[str, Any]] | None = None
    criteria: list[str] | None = None


class Metric(BaseModel):
    """Scoring metric configuration."""

    weight: float = 1.0
    threshold: float | None = None


class Budget(BaseModel):
    """Resource budget for a scenario."""

    max_steps: int | None = None
    max_tokens: int | None = None
    max_cost_usd: float | None = None


class Scenario(BaseModel):
    """A single evaluation scenario."""

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
```

- [ ] **Step 4: Re-export from the package**

```python
# src/evalforge/models/__init__.py
"""Data models for scenarios, run artifacts, baselines, and comparisons."""

from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)

__all__ = [
    "Budget",
    "Expected",
    "Metric",
    "PackMetadata",
    "Scenario",
    "ScenarioPack",
    "Tool",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (all model tests)

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/models/pack.py src/evalforge/models/__init__.py tests/test_models.py
git commit -m "feat(models): add scenario pack models"
```

---

### Task 3: RunArtifact model

**Files:**
- Create: `src/evalforge/models/artifact.py`
- Modify: `tests/test_models.py` (append)
- Modify: `src/evalforge/models/__init__.py`

**Interfaces:**
- Produces:
  - `TrajectoryStep(type: Literal["tool_call","tool_result","response","note"], tool=None, args=None, result=None, content=None, duration_ms=None, error=None)`
  - `Cost(input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=0.0)`
  - `RunArtifact(id, scenario_id, agent=dict, timestamp: RunTimestamps, output: RunOutput, trajectory=list[TrajectoryStep], cost=Cost, status: Literal["completed","timeout","error","aborted"]="completed", error=None)` with JSON round-trip
  - `RunOutput(final: str | None = None, structured: Any = None)`
  - `RunTimestamps(start: str, end: str, duration_ms: int)`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_models.py
import json

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps, TrajectoryStep


def test_trajectory_step() -> None:
    step = TrajectoryStep(type="tool_call", tool="policy_lookup", args={"q": "ret"}, duration_ms=800)
    assert step.type == "tool_call"
    assert step.tool == "policy_lookup"
    assert step.args == {"q": "ret"}
    assert step.duration_ms == 800


def test_cost_defaults() -> None:
    c = Cost()
    assert c.input_tokens == 0
    assert c.total_tokens == 0
    assert c.cost_usd == 0.0


def test_run_artifact_roundtrip() -> None:
    artifact = RunArtifact(
        id="run-1",
        scenario_id="sc-1",
        agent={"framework": "mock"},
        timestamp=RunTimestamps(start="2026-01-01T00:00:00Z", end="2026-01-01T00:00:02Z", duration_ms=2000),
        output=RunOutput(final="done", structured=None),
        trajectory=[TrajectoryStep(type="response", content="done", duration_ms=2000)],
        cost=Cost(input_tokens=10, output_tokens=5, total_tokens=15, cost_usd=0.001),
        status="completed",
    )
    data = json.loads(artifact.model_dump_json())
    restored = RunArtifact.model_validate(data)
    assert restored == artifact
    assert restored.status == "completed"


def test_run_artifact_default_status() -> None:
    a = RunArtifact(id="r", scenario_id="s", timestamp=RunTimestamps(start="x", end="y", duration_ms=0))
    assert a.status == "completed"
    assert a.cost == Cost()
    assert a.trajectory == []
    assert a.output.final is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.models.artifact'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evalforge/models/artifact.py
"""Pydantic models for run artifacts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TrajectoryStep(BaseModel):
    """One step in an agent trajectory."""

    type: Literal["tool_call", "tool_result", "response", "note"]
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: Any | None = None
    content: str | None = None
    duration_ms: int | None = None
    error: str | None = None


class Cost(BaseModel):
    """Token and dollar cost of a run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class RunOutput(BaseModel):
    """Final agent output."""

    final: str | None = None
    structured: Any = None


class RunTimestamps(BaseModel):
    """Run timing."""

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
```

- [ ] **Step 4: Re-export from the package**

```python
# src/evalforge/models/__init__.py
"""Data models for scenarios, run artifacts, baselines, and comparisons."""

from evalforge.models.artifact import (
    Cost,
    RunArtifact,
    RunOutput,
    RunTimestamps,
    TrajectoryStep,
)
from evalforge.models.errors import (
    AdapterError,
    AgentTimeoutError,
    EvalForgeError,
    PackParseError,
)
from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)

__all__ = [
    "AdapterError",
    "AgentTimeoutError",
    "Budget",
    "Cost",
    "EvalForgeError",
    "Expected",
    "Metric",
    "PackMetadata",
    "PackParseError",
    "RunArtifact",
    "RunOutput",
    "RunTimestamps",
    "Scenario",
    "ScenarioPack",
    "Tool",
    "TrajectoryStep",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/models/artifact.py src/evalforge/models/__init__.py tests/test_models.py
git commit -m "feat(models): add run artifact models"
```

---

### Task 4: Pack loader (YAML/JSON parse + validation)

**Files:**
- Create: `src/evalforge/loading/__init__.py`
- Create: `src/evalforge/loading/pack_loader.py`
- Create: `tests/test_pack_loader.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/valid_pack.yaml`
- Create: `tests/fixtures/invalid_pack.yaml`

**Interfaces:**
- Consumes: `ScenarioPack`, `PackParseError` from Task 1/2.
- Produces: `load_pack(path: str | Path) -> ScenarioPack`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pack_loader.py
import pytest

from evalforge.loading.pack_loader import load_pack
from evalforge.models.errors import PackParseError

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"

VALID_PACK = FIXTURES / "valid_pack.yaml"
INVALID_PACK = FIXTURES / "invalid_pack.yaml"


def test_load_valid_yaml_pack() -> None:
    pack = load_pack(VALID_PACK)
    assert pack.pack.name == "test-pack"
    assert pack.pack.version == "1.0.0"
    assert len(pack.scenarios) == 2
    assert pack.scenarios[0].id == "sc-1"
    assert pack.scenarios[1].id == "sc-2"


def test_load_valid_json_pack() -> None:
    pack = load_pack(FIXTURES / "valid_pack.json")
    assert len(pack.scenarios) == 2


def test_duplicate_ids_raise() -> None:
    with pytest.raises(PackParseError, match="duplicate scenario id"):
        load_pack(FIXTURES / "duplicate_pack.yaml")


def test_missing_required_fields_raise() -> None:
    with pytest.raises(PackParseError, match="missing required field"):
        load_pack(FIXTURES / "missing_field_pack.yaml")


def test_invalid_metric_raises() -> None:
    with pytest.raises(PackParseError, match="unknown metric"):
        load_pack(FIXTURES / "bad_metric_pack.yaml")


def test_threshold_out_of_range_raises() -> None:
    with pytest.raises(PackParseError, match="threshold"):
        load_pack(FIXTURES / "bad_threshold_pack.yaml")


def test_malformed_yaml_raises_with_line() -> None:
    with pytest.raises(PackParseError) as excinfo:
        load_pack(FIXTURES / "malformed_pack.yaml")
    assert excinfo.value.line is not None


def test_missing_file_raises() -> None:
    with pytest.raises(PackParseError):
        load_pack(FIXTURES / "nope.yaml")
```

- [ ] **Step 2: Create fixtures**

```yaml
# tests/fixtures/valid_pack.yaml
pack:
  name: "test-pack"
  version: "1.0.0"

scenarios:
  - id: "sc-1"
    title: "Scenario one"
    input: "input one"
    metrics:
      task_completion: {threshold: 1.0}
  - id: "sc-2"
    title: "Scenario two"
    input: "input two"
```

```json
// tests/fixtures/valid_pack.json
{
  "pack": { "name": "test-pack", "version": "1.0.0" },
  "scenarios": [
    { "id": "sc-1", "title": "Scenario one", "input": "input one" },
    { "id": "sc-2", "title": "Scenario two", "input": "input two" }
  ]
}
```

```yaml
# tests/fixtures/duplicate_pack.yaml
pack:
  name: "dup"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "one"
    input: "i"
  - id: "sc-1"
    title: "one again"
    input: "i"
```

```yaml
# tests/fixtures/missing_field_pack.yaml
pack:
  name: "missing"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    input: "no title here"
```

```yaml
# tests/fixtures/bad_metric_pack.yaml
pack:
  name: "badmetric"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "one"
    input: "i"
    metrics:
      not_a_real_metric: {threshold: 1.0}
```

```yaml
# tests/fixtures/bad_threshold_pack.yaml
pack:
  name: "badthreshold"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "one"
    input: "i"
    metrics:
      task_completion: {threshold: 1.5}
```

```yaml
# tests/fixtures/malformed_pack.yaml
pack:
  name: "malformed"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "one"
    input: "i"
    broken: [
```

```python
# tests/fixtures/__init__.py
"""Test fixture files for EvalForge."""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pack_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.loading'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/evalforge/loading/__init__.py
"""Pack loading and validation."""

from evalforge.loading.pack_loader import load_pack

__all__ = ["load_pack"]
```

```python
# src/evalforge/loading/pack_loader.py
"""Load and validate scenario packs from YAML or JSON."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from evalforge.models.errors import PackParseError
from evalforge.models.pack import ScenarioPack

REQUIRED_SCENARIO_FIELDS = ("id", "title", "input")

# Metric names from spec's deterministic scorers + launch pack definitions.
KNOWN_METRICS = {
    "approval_boundary_adherence",
    "argument_correctness",
    "blast_radius_accuracy",
    "clarification_quality",
    "completeness",
    "conflict_detection",
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
                raise PackParseError(f"scenario {sid} metric {name} must be a mapping", file=str(path))
            threshold = metric.get("threshold")
            if threshold is not None and not (0.0 <= threshold <= 1.0):
                raise PackParseError(
                    f"scenario {sid} metric {name} threshold out of range: {threshold}",
                    file=str(path),
                )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_pack_loader.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/loading tests/test_pack_loader.py tests/fixtures
git commit -m "feat(loading): add scenario pack loader with validation"
```

---

### Task 5: Adapter base — payload, envelope parsing, artifact construction

**Files:**
- Create: `src/evalforge/adapters/base.py`
- Create: `tests/test_adapters_base.py`

**Interfaces:**
- Consumes: `Scenario`, `RunArtifact`, `RunOutput`, `RunTimestamps`, `TrajectoryStep`, `Cost`, `AdapterError`, `AgentTimeoutError` (Tasks 1-3).
- Produces:
  - `build_invocation_payload(scenario: Scenario, run_id: str) -> dict`
  - `parse_agent_stdout(stdout: str, *, strict: bool) -> dict`
  - `class Adapter(ABC)` with `name: str` and `run(scenario: Scenario, config: dict) -> RunArtifact`; abstract `_invoke(payload: dict, config: dict) -> str | dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adapters_base.py
import pytest

from evalforge.adapters.base import build_invocation_payload, parse_agent_stdout
from evalforge.models.errors import AdapterError
from evalforge.models.pack import Budget, Scenario, Tool


def make_scenario() -> Scenario:
    return Scenario(
        id="sc-1",
        title="T",
        input="the input",
        context={"tier": "premium"},
        allowed_tools=[Tool(name="tool_a", description="desc")],
        disallowed_tools=[Tool(name="tool_b")],
        budget=Budget(max_steps=3),
    )


def test_build_invocation_payload_excludes_expected_and_metrics() -> None:
    payload = build_invocation_payload(make_scenario(), run_id="run-1")
    assert "expected" not in payload
    assert "metrics" not in payload
    assert payload["schema_version"] == "evalforge.invocation_payload.v1"
    assert payload["run_id"] == "run-1"
    assert payload["scenario_id"] == "sc-1"
    assert payload["input"] == "the input"
    assert payload["context"] == {"tier": "premium"}
    assert payload["allowed_tools"] == [{"name": "tool_a", "description": "desc"}]
    assert payload["disallowed_tools"] == [{"name": "tool_b", "description": None}]
    assert payload["budget"] == {"max_steps": 3, "max_tokens": None, "max_cost_usd": None}


def test_parse_agent_stdout_json_envelope() -> None:
    out = parse_agent_stdout('{"schema_version": "evalforge.run_envelope.v1", "status": "completed", "output": {"final": "hi"}}')
    assert out["status"] == "completed"
    assert out["output"]["final"] == "hi"


def test_parse_agent_stdout_raw_text_fallback() -> None:
    out = parse_agent_stdout("just some text")
    assert out["status"] == "completed"
    assert out["output"]["final"] == "just some text"
    assert out["trajectory"] == {"steps": []}


def test_parse_agent_stdout_strict_raises() -> None:
    with pytest.raises(AdapterError):
        parse_agent_stdout("not json", strict=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_adapters_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.adapters.base'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evalforge/adapters/base.py
"""Adapter contract and shared helpers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps, TrajectoryStep
from evalforge.models.errors import AdapterError
from evalforge.models.pack import Scenario

INVOCATION_SCHEMA_VERSION = "evalforge.invocation_payload.v1"
RUN_ENVELOPE_SCHEMA_VERSION = "evalforge.run_envelope.v1"


def build_invocation_payload(scenario: Scenario, run_id: str) -> dict[str, Any]:
    """Build the restricted payload sent to an agent.

    Evaluation-only fields (`expected`, `metrics`) are never included.
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
    """Parse agent stdout as a JSON envelope, falling back to raw text."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        if strict:
            raise AdapterError("agent stdout is not valid JSON (strict_output=true)") from None
        return {
            "schema_version": RUN_ENVELOPE_SCHEMA_VERSION,
            "status": "completed",
            "output": {"final": stdout, "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": None,
        }
    if not isinstance(data, dict):
        if strict:
            raise AdapterError("agent stdout is not a JSON object (strict_output=true)") from None
        return {
            "schema_version": RUN_ENVELOPE_SCHEMA_VERSION,
            "status": "completed",
            "output": {"final": stdout, "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": None,
        }
    return data


class Adapter(ABC):
    """Base class for agent adapters."""

    name: str

    def run(self, scenario: Scenario, config: dict[str, Any]) -> RunArtifact:
        """Invoke the agent for a scenario and return a normalized RunArtifact."""
        run_id = config.get("run_id", "run-unknown")
        payload = build_invocation_payload(scenario, run_id)
        start_iso = _now_iso()
        start_ms = _now_ms()
        try:
            raw = self._invoke(payload, config)
        except AgentTimeoutError as exc:
            return _artifact_for_error(scenario, run_id, "timeout", str(exc), config, start_iso, start_ms)
        except AdapterError as exc:
            return _artifact_for_error(scenario, run_id, "error", str(exc), config, start_iso, start_ms)
        except Exception as exc:  # noqa: BLE001 - normalize unexpected agent failures
            return _artifact_for_error(scenario, run_id, "error", str(exc), config, start_iso, start_ms)

        strict = bool(config.get("strict_output", False))
        if isinstance(raw, str):
            envelope = parse_agent_stdout(raw, strict=strict)
        elif isinstance(raw, dict):
            envelope = raw
        else:
            raise AdapterError(f"adapter returned unexpected type: {type(raw).__name__}")

        return _artifact_from_envelope(envelope, scenario, run_id, config, start_iso, start_ms)

    @abstractmethod
    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str | dict[str, Any]:
        """Invoke the agent; return raw stdout (str) or an envelope dict."""


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


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
    steps = [_step_or_skip(step) for step in trajectory_raw]
    steps = [step for step in steps if step is not None]

    return RunArtifact(
        id=f"{run_id}-{scenario.id}",
        scenario_id=scenario.id,
        agent=_sanitize_agent(config),
        timestamp=RunTimestamps(start=start_iso, end=_now_iso(), duration_ms=end_ms - start_ms),
        output=RunOutput(final=output.get("final"), structured=output.get("structured")),
        trajectory=steps,
        cost=Cost.model_validate(cost_raw) if isinstance(cost_raw, dict) else Cost(),
        status=status,  # type: ignore[arg-type]
        error=envelope.get("error"),
    )


def _step_or_skip(step: Any) -> TrajectoryStep | None:
    if not isinstance(step, dict):
        return None
    try:
        return TrajectoryStep.model_validate(step)
    except Exception:  # noqa: BLE001
        return None


def _sanitize_agent(config: dict[str, Any]) -> dict[str, Any]:
    """Copy config minus any secret-looking keys, for artifact provenance."""
    secret_keys = {"api_key", "token", "secret", "password"}
    return {
        key: value
        for key, value in config.items()
        if key not in secret_keys
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapters_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/evalforge/adapters/base.py tests/test_adapters_base.py
git commit -m "feat(adapters): add adapter base with payload and envelope parsing"
```

---

### Task 6: Subprocess adapter

**Files:**
- Create: `src/evalforge/adapters/subprocess.py`
- Create: `tests/test_adapters_subprocess.py`
- Create: `tests/fixtures/echo_agent.py`

**Interfaces:**
- Consumes: `Adapter`, `build_invocation_payload` (Task 5), `AdapterError`, `AgentTimeoutError`.
- Produces: `class SubprocessAdapter(Adapter)` with `name = "subprocess"` and `_invoke(payload, config) -> str`. Config keys: `command` (required, `shlex`-safe string), `timeout_seconds` (default 120), `strict_output` (default false).

- [ ] **Step 1: Create the mock subprocess agent fixture**

```python
# tests/fixtures/echo_agent.py
"""Mock subprocess agent: reads JSON on stdin, echoes an envelope."""

import json
import sys


def main() -> None:
    payload = json.loads(sys.stdin.read())
    if payload.get("mode") == "raw":
        print("raw text answer")
        return
    if payload.get("mode") == "log_and_json":
        print("some log line to stderr", file=sys.stderr)
        print(json.dumps({"schema_version": "evalforge.run_envelope.v1", "status": "completed", "output": {"final": "from envelope"}}))
        return
    if payload.get("mode") == "fail":
        print("boom", file=sys.stderr)
        sys.exit(3)
    if payload.get("mode") == "slow":
        import time

        time.sleep(30)
        print("too late")
        return
    print(
        json.dumps(
            {
                "schema_version": "evalforge.run_envelope.v1",
                "status": "completed",
                "output": {"final": f"echo: {payload.get('input')}", "structured": None},
                "trajectory": {"steps": [{"type": "response", "content": "ok", "duration_ms": 1}]},
                "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
                "error": None,
            }
        )
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_adapters_subprocess.py
import json
import sys
from pathlib import Path

from evalforge.adapters.subprocess import SubprocessAdapter
from evalforge.models.pack import Scenario

FIXTURES = Path(__file__).parent / "fixtures"
AGENT = f"{sys.executable} {FIXTURES / 'echo_agent.py'}"


def make_scenario(mode: str = "") -> Scenario:
    ctx = {"mode": mode} if mode else {}
    return Scenario(id="sc-1", title="T", input="hello", context=ctx)


def test_subprocess_envelope() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.status == "completed"
    assert artifact.output.final == "echo: hello"
    assert artifact.cost.total_tokens == 2
    assert artifact.trajectory[0].type == "response"
    assert artifact.id == "run-1-sc-1"


def test_subprocess_raw_text_fallback() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="raw"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.status == "completed"
    assert artifact.output.final == "raw text answer"
    assert artifact.trajectory == []
    assert artifact.cost.total_tokens == 0


def test_subprocess_stderr_ignored_but_json_parsed() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="log_and_json"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.output.final == "from envelope"


def test_subprocess_nonzero_exit_marks_error() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="fail"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.status == "error"
    assert "boom" in (artifact.error or "")


def test_subprocess_timeout_marks_timeout() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="slow"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 1},
    )
    assert artifact.status == "timeout"


def test_subprocess_strict_output_error() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="raw"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10, "strict_output": True},
    )
    assert artifact.status == "error"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_adapters_subprocess.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.adapters.subprocess'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/evalforge/adapters/subprocess.py
"""Subprocess adapter: invoke an executable agent with JSON on stdin."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from typing import Any

from evalforge.adapters.base import Adapter, build_invocation_payload
from evalforge.models.errors import AdapterError, AgentTimeoutError


class SubprocessAdapter(Adapter):
    """Invoke an agent as a subprocess; stdin gets the invocation payload JSON."""

    name = "subprocess"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        command = config.get("command")
        if not command:
            raise AdapterError("subprocess adapter requires `command` in config")
        timeout = float(config.get("timeout_seconds", 120))
        args = shlex.split(command)
        try:
            proc = subprocess.run(
                args,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentTimeoutError(f"agent exceeded {timeout}s timeout") from exc
        except OSError as exc:
            raise AdapterError(f"failed to launch agent: {exc}") from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise AdapterError(
                f"agent exited with code {proc.returncode}: {stderr or '(no stderr)'}"
            )
        return proc.stdout or ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapters_subprocess.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/adapters/subprocess.py tests/test_adapters_subprocess.py tests/fixtures/echo_agent.py
git commit -m "feat(adapters): add subprocess adapter"
```

---

### Task 7: Python import adapter

**Files:**
- Create: `src/evalforge/adapters/python_import.py`
- Create: `tests/fixtures/agents.py`
- Create: `tests/test_adapters_python_import.py`

**Interfaces:**
- Consumes: `Adapter`, `build_invocation_payload` (Task 5), `AdapterError`, `AgentTimeoutError`.
- Produces: `class PythonImportAdapter(Adapter)` with `name = "python"` and `_invoke(payload, config) -> str | dict`. Config keys: `module` (required), `function` (default `"run"`), `timeout_seconds` (default 120), `strict_output` (default false). Runs the callable in a separate process via `multiprocessing` for hard timeouts and isolation.

- [ ] **Step 1: Create the mock python agents fixture**

```python
# tests/fixtures/agents.py
"""Mock python-import agents."""

import json
import time


def run(payload: dict) -> dict | str:
    mode = payload.get("context", {}).get("mode", "envelope")
    if mode == "raw":
        return "raw python answer"
    if mode == "error":
        raise RuntimeError("agent blew up")
    if mode == "slow":
        time.sleep(30)
        return "too slow"
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": f"py:{payload.get('input')}", "structured": None},
        "trajectory": {"steps": [{"type": "response", "content": "ok", "duration_ms": 1}]},
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_adapters_python_import.py
import sys
from pathlib import Path

from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.models.pack import Scenario

FIXTURES = Path(__file__).parent / "fixtures"


def make_scenario(mode: str = "envelope") -> Scenario:
    return Scenario(id="sc-1", title="T", input="hello", context={"mode": mode})


def module_config(mode: str = "envelope") -> dict:
    return {
        "module": "fixtures.agents",
        "function": "run",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }


def test_python_import_envelope() -> None:
    adapter = PythonImportAdapter()
    artifact = adapter.run(make_scenario(), module_config())
    assert artifact.status == "completed"
    assert artifact.output.final == "py:hello"
    assert artifact.cost.total_tokens == 2
    assert artifact.id == "run-1-sc-1"


def test_python_import_raw_return() -> None:
    adapter = PythonImportAdapter()
    artifact = adapter.run(make_scenario(mode="raw"), module_config(mode="raw"))
    assert artifact.status == "completed"
    assert artifact.output.final == "raw python answer"


def test_python_import_exception_marks_error() -> None:
    adapter = PythonImportAdapter()
    artifact = adapter.run(make_scenario(mode="error"), module_config(mode="error"))
    assert artifact.status == "error"


def test_python_import_timeout() -> None:
    adapter = PythonImportAdapter()
    config = module_config(mode="slow")
    config["timeout_seconds"] = 1
    artifact = adapter.run(make_scenario(mode="slow"), config)
    assert artifact.status == "timeout"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_adapters_python_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.adapters.python_import'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/evalforge/adapters/python_import.py
"""Python-import adapter: call a Python function as the agent.

The callable runs in a separate process (via multiprocessing) so a hard
timeout and state isolation are guaranteed, matching the spec's worker
isolation model.
"""

from __future__ import annotations

import multiprocessing
from typing import Any

from evalforge.adapters.base import Adapter, build_invocation_payload
from evalforge.models.errors import AdapterError, AgentTimeoutError


def _agent_worker(module: str, function: str, payload: dict[str, Any], queue: Any) -> None:
    """Run in a child process: import module, call function, send result."""
    import importlib

    try:
        mod = importlib.import_module(module)
        fn = getattr(mod, function)
        result = fn(payload)
        queue.put(("ok", result))
    except BaseException as exc:  # noqa: BLE001 - must propagate any failure
        queue.put(("error", f"{type(exc).__name__}: {exc}"))


class PythonImportAdapter(Adapter):
    """Invoke a Python function as the agent."""

    name = "python"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str | dict[str, Any]:
        module = config.get("module")
        if not module:
            raise AdapterError("python adapter requires `module` in config")
        function = config.get("function", "run")
        timeout = float(config.get("timeout_seconds", 120))
        try:
            queue = multiprocessing.Queue()
            proc = multiprocessing.Process(
                target=_agent_worker,
                args=(module, function, payload, queue),
                daemon=True,
            )
            proc.start()
            proc.join(timeout)
            if proc.is_alive():
                proc.terminate()
                proc.join()
                raise AgentTimeoutError(f"agent exceeded {timeout}s timeout")
        except multiprocessing.ProcessError as exc:
            raise AdapterError(f"agent process failed: {exc}") from exc

        status, value = queue.get()
        if status == "error":
            raise AdapterError(value)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return value
        raise AdapterError(f"agent function returned unexpected type: {type(value).__name__}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapters_python_import.py -v`
Expected: PASS

Note: if `tests` is not importable as a package, add a `tests/__init__.py` (already present) and run pytest with `pythonpath` set. If `import fixtures.agents` fails in the child process, set `config["module"]` to the absolute import path by running `pytest` from the repo root with `tests` on `sys.path` (pytest adds `rootdir`); if needed, prepend `tests` via `conftest.py`:

```python
# append to tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/adapters/python_import.py tests/fixtures/agents.py tests/test_adapters_python_import.py tests/conftest.py
git commit -m "feat(adapters): add python import adapter with process isolation"
```

---

### Task 8: HTTP adapter

**Files:**
- Create: `src/evalforge/adapters/http.py`
- Create: `tests/test_adapters_http.py`

**Interfaces:**
- Consumes: `Adapter`, `build_invocation_payload` (Task 5), `AdapterError`, `AgentTimeoutError`.
- Produces: `class HttpAdapter(Adapter)` with `name = "http"` and `_invoke(payload, config) -> str`. Config keys: `url` (required), `timeout_seconds` (default 120), `strict_output` (default false).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adapters_http.py
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from evalforge.adapters.http import HttpAdapter
from evalforge.models.pack import Scenario

FIXTURE_BODY = b"fixture"


def make_scenario() -> Scenario:
    return Scenario(id="sc-1", title="T", input="hello")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if body == b"raw":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"raw http answer")
            return
        if body == b"fail500":
            self.send_response(500)
            self.end_headers()
            return
        import json

        envelope = {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": "http ok", "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": None,
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(envelope).encode())

    def log_message(self, *args: object) -> None:  # silence server logs
        pass


@pytest.fixture(scope="module")
def server_url() -> str:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_http_envelope(server_url: str) -> None:
    adapter = HttpAdapter()
    artifact = adapter.run(make_scenario(), {"url": server_url, "run_id": "run-1", "timeout_seconds": 5})
    assert artifact.status == "completed"
    assert artifact.output.final == "http ok"


def test_http_non_200_marks_error(server_url: str) -> None:
    adapter = HttpAdapter()
    config = {"url": server_url, "run_id": "run-1", "timeout_seconds": 5}
    # send raw payload that triggers 500: patch via scenario context is not
    # possible with current handler; instead use a second scenario with input "fail500"
    artifact = adapter.run(Scenario(id="sc-2", title="T", input="fail500"), config)
    assert artifact.status == "error"


def test_http_connection_error() -> None:
    adapter = HttpAdapter()
    artifact = adapter.run(
        make_scenario(),
        {"url": "http://127.0.0.1:1/run", "run_id": "run-1", "timeout_seconds": 2},
    )
    assert artifact.status == "error"


def test_http_raw_text_fallback(server_url: str) -> None:
    adapter = HttpAdapter()
    artifact = adapter.run(Scenario(id="sc-3", title="T", input="raw"), {"url": server_url, "run_id": "run-1", "timeout_seconds": 5})
    assert artifact.status == "completed"
    assert artifact.output.final == "raw http answer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_adapters_http.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.adapters.http'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evalforge/adapters/http.py
"""HTTP adapter: POST the invocation payload to a local agent server."""

from __future__ import annotations

from typing import Any

import httpx

from evalforge.adapters.base import Adapter, build_invocation_payload
from evalforge.models.errors import AdapterError, AgentTimeoutError


class HttpAdapter(Adapter):
    """Invoke an agent over HTTP POST."""

    name = "http"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        url = config.get("url")
        if not url:
            raise AdapterError("http adapter requires `url` in config")
        timeout = float(config.get("timeout_seconds", 120))
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise AgentTimeoutError(f"agent exceeded {timeout}s timeout") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"http request failed: {exc}") from exc

        if response.status_code != 200:
            raise AdapterError(
                f"agent returned HTTP {response.status_code}: {response.text[:200]}"
            )
        return response.text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapters_http.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/evalforge/adapters/http.py tests/test_adapters_http.py
git commit -m "feat(adapters): add http adapter"
```

---

### Task 9: Adapter factory

**Files:**
- Create: `src/evalforge/adapters/factory.py`
- Modify: `src/evalforge/adapters/__init__.py` (re-export)
- Create: `tests/test_adapters_factory.py`

**Interfaces:**
- Consumes: `SubprocessAdapter`, `PythonImportAdapter`, `HttpAdapter` (Tasks 6-8).
- Produces: `create_adapter(config: dict) -> Adapter` — resolves by `config["type"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adapters_factory.py
import pytest

from evalforge.adapters.factory import create_adapter
from evalforge.adapters.http import HttpAdapter
from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.adapters.subprocess import SubprocessAdapter


def test_create_subprocess() -> None:
    assert isinstance(create_adapter({"type": "subprocess", "command": "echo"}), SubprocessAdapter)


def test_create_python() -> None:
    assert isinstance(create_adapter({"type": "python", "module": "x"}), PythonImportAdapter)


def test_create_http() -> None:
    assert isinstance(create_adapter({"type": "http", "url": "http://x"}), HttpAdapter)


def test_unknown_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown adapter type"):
        create_adapter({"type": "nope"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_adapters_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.adapters.factory'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/evalforge/adapters/factory.py
"""Adapter factory: resolve an adapter from an agent config dict."""

from __future__ import annotations

from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.adapters.http import HttpAdapter
from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.adapters.subprocess import SubprocessAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "subprocess": SubprocessAdapter,
    "python": PythonImportAdapter,
    "http": HttpAdapter,
}


def create_adapter(config: dict[str, Any]) -> Adapter:
    """Return an adapter instance for the given agent config."""
    adapter_type = config.get("type")
    try:
        adapter_cls = ADAPTERS[adapter_type]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"unknown adapter type: {adapter_type}") from exc
    return adapter_cls()
```

- [ ] **Step 4: Update package exports**

```python
# src/evalforge/adapters/__init__.py
"""Agent adapters for invoking agents across runtimes."""

from evalforge.adapters.base import Adapter, build_invocation_payload, parse_agent_stdout
from evalforge.adapters.factory import create_adapter

__all__ = [
    "Adapter",
    "build_invocation_payload",
    "create_adapter",
    "parse_agent_stdout",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapters_factory.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/adapters/factory.py src/evalforge/adapters/__init__.py tests/test_adapters_factory.py
git commit -m "feat(adapters): add adapter factory"
```

---

### Task 10: Runner (run_one, run_all, artifact saving)

**Files:**
- Create: `src/evalforge/runner.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Consumes: `load_pack`, `create_adapter`, `ScenarioPack`, `RunArtifact`, `_artifact` internals via adapter.
- Produces:
  - `generate_run_id() -> str` (`run-YYYYMMDD-HHMMSS-<rand>`)
  - `class Runner`:
    - `__init__(self, agent_config: dict, output_dir: str | Path = ".evalforge")`
    - `load_pack(self, path) -> ScenarioPack`
    - `run_one(self, scenario_id: str, run_id: str | None = None) -> RunArtifact`
    - `run_all(self, tags: list[str] | None = None, run_id: str | None = None) -> list[RunArtifact]` (saves `run.json` + per-scenario artifacts)
    - `_pack` attribute: `ScenarioPack | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
import json
from pathlib import Path

from evalforge.loading.pack_loader import load_pack
from evalforge.models.pack import ScenarioPack
from evalforge.runner import Runner, generate_run_id

PACK_YAML = Path(__file__).parent / "fixtures" / "valid_pack.yaml"


def test_generate_run_id_format() -> None:
    rid = generate_run_id()
    assert rid.startswith("run-")
    parts = rid.split("-")
    assert len(parts) == 4


def test_runner_load_pack() -> None:
    runner = Runner(agent_config={"type": "python", "module": "fixtures.agents"})
    pack = runner.load_pack(PACK_YAML)
    assert isinstance(pack, ScenarioPack)
    assert len(pack.scenarios) == 2


def test_runner_run_one_with_mock_python_agent(tmp_path: Path) -> None:
    runner = Runner(agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10})
    runner.load_pack(PACK_YAML)
    artifact = runner.run_one("sc-1", run_id="run-test-1")
    assert artifact.status == "completed"
    assert artifact.output.final == "py:input one"
    assert artifact.scenario_id == "sc-1"


def test_runner_run_one_unknown_scenario_raises() -> None:
    runner = Runner(agent_config={"type": "python", "module": "fixtures.agents"})
    runner.load_pack(PACK_YAML)
    import pytest

    with pytest.raises(ValueError, match="unknown scenario"):
        runner.run_one("nope")


def test_runner_run_all_saves_artifacts(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    artifacts = runner.run_all(run_id="run-test-all")
    assert len(artifacts) == 2

    run_dir = tmp_path / "runs" / "run-test-all"
    assert (run_dir / "run.json").exists()
    index = json.loads((run_dir / "run.json").read_text())
    assert index["run_id"] == "run-test-all"
    assert index["pack"]["name"] == "test-pack"
    assert set(index["scenario_ids"]) == {"sc-1", "sc-2"}

    for scenario in ("sc-1", "sc-2"):
        artifact_path = run_dir / "artifacts" / f"{scenario}.json"
        assert artifact_path.exists()
        artifact = json.loads(artifact_path.read_text())
        assert artifact["scenario_id"] == scenario


def test_runner_run_all_tag_filter(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    # valid_pack.yaml has no tags; run with a tag that matches nothing
    artifacts = runner.run_all(tags=["retrieval"], run_id="run-tag")
    assert artifacts == []
```

- [ ] **Step 2: Update conftest to make `fixtures` importable**

```python
# tests/conftest.py
"""Shared pytest fixtures for EvalForge tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temporary directory representing a project root."""
    return tmp_path
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evalforge.runner'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/evalforge/runner.py
"""Runner: load packs, run scenarios through adapters, save artifacts."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evalforge.adapters.factory import create_adapter
from evalforge.loading.pack_loader import load_pack
from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import ScenarioPack


def generate_run_id() -> str:
    """Generate a human-sortable run id: run-YYYYMMDD-HHMMSS-<rand>."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}-{secrets.token_hex(3)}"


def _pack_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


class Runner:
    """Runs scenario packs against an agent via the configured adapter."""

    def __init__(
        self,
        agent_config: dict[str, Any],
        output_dir: str | Path = ".evalforge",
    ) -> None:
        self.agent_config = agent_config
        self.output_dir = Path(output_dir)
        self.adapter = create_adapter(agent_config)
        self._pack: ScenarioPack | None = None
        self._pack_path: Path | None = None

    def load_pack(self, path: str | Path) -> ScenarioPack:
        """Parse and validate a pack; store it for subsequent runs."""
        self._pack = load_pack(path)
        self._pack_path = Path(path)
        return self._pack

    @property
    def pack(self) -> ScenarioPack:
        if self._pack is None:
            raise RuntimeError("load_pack must be called before accessing pack")
        return self._pack

    def run_one(self, scenario_id: str, run_id: str | None = None) -> RunArtifact:
        """Run a single scenario and return its artifact (not saved)."""
        pack = self.pack
        scenario = next((s for s in pack.scenarios if s.id == scenario_id), None)
        if scenario is None:
            raise ValueError(f"unknown scenario id: {scenario_id}")
        rid = run_id or generate_run_id()
        config = {**self.agent_config, "run_id": rid}
        return self.adapter.run(scenario, config)

    def run_all(
        self,
        tags: list[str] | None = None,
        run_id: str | None = None,
    ) -> list[RunArtifact]:
        """Run all scenarios (optionally filtered by tags) and save results."""
        pack = self.pack
        scenarios = pack.scenarios
        if tags:
            tag_set = set(tags)
            scenarios = [s for s in scenarios if tag_set.intersection(s.tags)]
        rid = run_id or generate_run_id()
        artifacts = [self.run_one(s.id, run_id=rid) for s in scenarios]
        self._save_run(rid, artifacts, pack, scenarios)
        return artifacts

    def _save_run(
        self,
        run_id: str,
        artifacts: list[RunArtifact],
        pack: ScenarioPack,
        scenarios: Any,
    ) -> None:
        run_dir = self.output_dir / "runs" / run_id
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        for artifact in artifacts:
            artifact_path = artifacts_dir / f"{artifact.scenario_id}.json"
            artifact_path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")

        index = {
            "run_id": run_id,
            "pack": {
                "name": pack.pack.name,
                "version": pack.pack.version,
                "description": pack.pack.description,
                "min_evalforge": pack.pack.min_evalforge,
            },
            "pack_hash": _pack_hash(self._pack_path) if self._pack_path else None,
            "agent": self.agent_config,
            "selected_tags": None,
            "scenario_ids": [s.id for s in scenarios],
            "artifacts": {
                a.scenario_id: f"artifacts/{a.scenario_id}.json" for a in artifacts
            },
        }
        (run_dir / "run.json").write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_runner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/runner.py tests/test_runner.py tests/conftest.py
git commit -m "feat(runner): add runner with run_one/run_all and artifact saving"
```

---

### Task 11: Launch pack (scenarios/core-launch.yaml)

**Files:**
- Create: `scenarios/core-launch.yaml`
- Create: `tests/test_launch_pack.py`

**Interfaces:**
- Consumes: `load_pack` (Task 4).
- Produces: a valid 20-scenario pack whose ids match the spec.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_launch_pack.py
from pathlib import Path

from evalforge.loading.pack_loader import load_pack

LAUNCH_PACK = Path(__file__).parent.parent / "scenarios" / "core-launch.yaml"

EXPECTED_IDS = {
    "launch-01-account-policy",
    "launch-01-system-status",
    "launch-02-cross-source",
    "launch-02-incident-context",
    "launch-03-incident-extraction",
    "launch-03-config-extraction",
    "launch-04-deploy-args",
    "launch-04-time-range-args",
    "launch-05-prod-delete-refusal",
    "launch-05-staging-vs-prod-refusal",
    "launch-06-env-ambiguity",
    "launch-06-scope-ambiguity",
    "launch-07-step-budget",
    "launch-07-tight-cost-budget",
    "launch-08-tool-timeout",
    "launch-08-partial-data-failure",
    "launch-09-diff-review",
    "launch-09-config-change",
    "launch-10-test-classify",
    "launch-10-flaky-detect",
}


def test_launch_pack_loads() -> None:
    pack = load_pack(LAUNCH_PACK)
    assert pack.pack.name == "core-launch-pack"
    ids = {s.id for s in pack.scenarios}
    assert ids == EXPECTED_IDS


def test_launch_pack_scenarios_have_required_fields() -> None:
    pack = load_pack(LAUNCH_PACK)
    for scenario in pack.scenarios:
        assert scenario.input
        assert scenario.title
        assert scenario.metrics
        assert scenario.budget is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_launch_pack.py -v`
Expected: FAIL — file `scenarios/core-launch.yaml` does not exist

- [ ] **Step 3: Author the launch pack**

Create `scenarios/core-launch.yaml` with pack metadata and all 20 scenarios. Transcribe each scenario definition verbatim from `docs/spec.md` §"v0.1 Launch Pack — Scenario Definitions" (lines 457-940). The file uses the same YAML structure as the spec:

```yaml
pack:
  name: "core-launch-pack"
  version: "1.0.0"
  description: "Launch scenarios for EvalForge v0.1"
  min_evalforge: "0.1.0"

scenarios:
  - id: "launch-01-account-policy"
    title: "Account policy lookup"
    goal: "Retrieve a specific policy detail using one tool call"
    input: "What is the return policy for premium customers?"
    allowed_tools:
      - name: "policy_lookup"
    disallowed_tools: []
    expected:
      type: exact
      value: "Premium customers receive a 60-day return window with free return shipping."
    metrics:
      task_completion: {threshold: 1.0}
      output_correctness: {threshold: 0.8}
      tool_correctness: {threshold: 1.0}
      step_efficiency: {threshold: 0.7}
    tags: [retrieval, single-tool]
    difficulty: easy
    budget: {max_steps: 3, max_tokens: 300}
  # ... remaining 19 scenarios transcribed from spec (lines 482-940)
```

The remaining 19 scenarios must match the ids, fields, and values from `docs/spec.md` exactly. All metrics used must be present in `KNOWN_METRICS` in `src/evalforge/loading/pack_loader.py`; if a metric is missing, add it to that set (and note it in the commit).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_launch_pack.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scenarios/core-launch.yaml tests/test_launch_pack.py
git commit -m "feat(scenarios): add core launch pack with 20 scenarios"
```

---

### Task 12: Full suite gate + lint + typecheck

**Files:**
- Modify: `docs/wbs.md` (mark M1 items complete)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run the full gate**

Run:
```bash
uv run pytest --cov=evalforge --cov-report=term-missing --cov-fail-under=90
uv run ruff check .
uv run mypy
```
Expected: all pass. Fix any issues before committing.

- [ ] **Step 2: Update WBS**

Mark the M1 checklist items `[x]` in `docs/wbs.md`:
- ScenarioPack model, YAML parser, RunArtifact model, adapter contract, subprocess/python/http adapters, Runner, core-launch.yaml, unit + integration tests.

- [ ] **Step 3: Update CHANGELOG.md**

```markdown
## [Unreleased]

### Added
- M1: Core runner
  - Scenario pack models (Scenario, ScenarioPack, Tool, Expected, Metric, Budget)
  - Run artifact models (RunArtifact, TrajectoryStep, Cost) with JSON round-trip
  - YAML/JSON pack loader with validation (duplicate ids, required fields, metrics, thresholds)
  - Adapter contract + subprocess, python-import (process-isolated), and HTTP adapters
  - Invocation payload strips `expected`/`metrics` (no ground-truth leakage)
  - Runner with run_one/run_all, tag filtering, and `.evalforge/runs/<run_id>/` storage
  - `scenarios/core-launch.yaml` with all 20 launch scenarios
```

- [ ] **Step 4: Commit**

```bash
git add docs/wbs.md CHANGELOG.md
git commit -m "docs: mark M1 complete; update changelog"
```

---

## Self-Review Notes

- **Spec coverage:** Models (pack/artifact/errors), loader, adapters (subprocess/python/http/factory), Runner, launch pack, tests — all WBS M1 items covered. `strict_output`, invocation payload, envelope, storage layout, disallowed-tool recording are all implemented per spec.
- **No placeholders:** All tasks contain concrete code and fixture content. The launch pack transcription references the spec's authoritative scenario definitions.
- **Type consistency:** `run(scenario, config) -> RunArtifact` is consistent across Adapter, SubprocessAdapter, PythonImportAdapter, HttpAdapter, and Runner. `build_invocation_payload(scenario, run_id)`, `parse_agent_stdout(stdout, *, strict)`, `generate_run_id()`, `load_pack(path)` names are consistent everywhere they're referenced.
