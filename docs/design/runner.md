# Core Runner — Design

Covers the core runner architecture, adapter contract, subprocess I/O contract, and data flow.

## Decisions

1. **Subprocess I/O contract:** EvalForge passes scenario JSON on stdin; agent
   writes a JSON envelope (`{output, trajectory, cost, status}`) to stdout.
   If stdout is not valid JSON, EvalForge falls back to treating raw text as
   the final output with an empty trajectory. This lets existing CLI agents
   produce valid artifacts without changes while enabling rich trajectories
   for agents that opt in.
2. **Launch pack pulled forward:** All 20 launch scenarios are authored in M1
   (`scenarios/core-launch.yaml`). M4/M5 now cover only mock agents, tests,
   and fixture data.
3. **Output strictness:** `strict_output` defaults to `false` for adoption.
   In strict mode, non-JSON stdout is an adapter error.

## Goal

Load scenario packs, invoke agents through adapters, and capture normalized
`RunArtifact`s. This is the execution spine everything else (scoring,
comparison, baselines) builds on.

## Architecture

Single-command flow, library-first:

```
pack YAML/JSON → ScenarioPack → Runner → adapter.run(scenario, config) → RunArtifact → save to .evalforge/runs/
```

### Agent Invocation Payload (No Ground-Truth Leakage)

EvalForge MUST NOT pass evaluation-only fields to the agent runtime. In
particular: `expected`, `metrics`, and scoring thresholds are **never** sent
to agents.

Adapters receive the full `Scenario` object (because EvalForge needs it for
validation and later scoring), but what gets transmitted to the agent is a
restricted payload:

```json
{
  "schema_version": "evalforge.invocation_payload.v1",
  "run_id": "run-20260730-001",
  "scenario_id": "launch-01-account-policy",
  "input": "What is the return policy for premium customers?",
  "context": {"customer_tier": "premium"},
  "allowed_tools": [{"name": "policy_lookup", "description": "Look up company policies by keyword"}],
  "disallowed_tools": [{"name": "customer_delete"}],
  "budget": {"max_steps": 3, "max_tokens": 500, "max_cost_usd": 0.05}
}
```

The agent can still decide how to solve the problem and which allowed tools to
call, but cannot directly read the rubric or expected answer.

## Components

### Models (`src/evalforge/models/`)

- **`pack.py`** — `Scenario` (id, title, goal, input, context,
  allowed_tools, disallowed_tools, expected, metrics, tags, difficulty,
  budget) and `ScenarioPack` (metadata: name, version, description,
  min_evalforge; scenarios list). Pydantic models.
- **`artifact.py`** — `TrajectoryStep` (type, tool, args, result, content,
  duration_ms), `Cost` (input/output/total tokens, cost_usd),
  `RunArtifact` (id, scenario_id, timestamps, output, trajectory, cost,
  status, error). Full JSON round-trip (serialize + deserialize).
- **`errors.py`** — `EvalForgeError` base with subclasses:
  `PackParseError` (file + line number), `AdapterError`, `AgentTimeoutError`.

### Parser (`src/evalforge/loading/`)

- **`pack_loader.py`** — YAML primary, JSON secondary. Validates: duplicate
  scenario IDs, missing required fields, valid metric names, threshold
  ranges (0.0–1.0). Raises `PackParseError` with line number on malformed YAML.
  Implementation note: PyYAML needs a custom loader to retain `Mark` info; if
  line/col fidelity becomes painful, switch to `ruamel.yaml`.

### Adapters (`src/evalforge/adapters/`)

- **`base.py`** — `Adapter` ABC with `run(scenario, config) -> RunArtifact`,
  per-scenario timeout enforcement, error capture/normalization. `config`
  carries adapter-specific settings (command, module/function, url,
  timeout_seconds).
- **`subprocess.py`** — stdin JSON in, JSON-envelope parse with raw-text
  fallback; handles timeout (status=`timeout`), crash (status=`error` +
  stderr), non-zero exit. Logs belong on stderr.
- **`python_import.py`** — import module, call function
  `run(payload)`, capture return value and exceptions.
  Timeout enforcement is implemented by running the callable in a separate
  process (hard timeouts + isolation).
- **`http.py`** — POST scenario JSON, handle connection errors, timeouts,
  non-200 responses.
- **`factory.py`** — resolve adapter from agent config by `type:`.

#### Subprocess JSON Envelope (v1)

If an agent opts in to rich output, it should write JSON *only* to stdout:

```json
{
  "schema_version": "evalforge.run_envelope.v1",
  "status": "completed",
  "output": {"final": "...", "structured": null},
  "trajectory": {"steps": []},
  "cost": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
  "error": null
}
```

Parsing rules:
- EvalForge first attempts to parse the entire stdout as JSON.
- If parsing fails, EvalForge treats stdout as raw text output (`output.final`)
  with an empty trajectory and null cost.
- Extra JSON fields are ignored for forward compatibility.

Strict mode:
- If `strict_output=true`, non-JSON stdout becomes a scenario error (`status="error"`).

### Runner (`src/evalforge/runner.py`)

- `Runner.load_pack(path)` — parse + validate.
- `run_one(scenario_id)` — run a single scenario, return `RunArtifact`.
- `run_all(tags=None)` — run pack, optional tag filter, save artifacts to
  `.evalforge/runs/`.

### Launch pack (`scenarios/core-launch.yaml`)

All 20 scenarios across 10 families:
1. Single-Tool Factual Retrieval
2. Multi-Tool Retrieval Synthesis
3. Structured JSON Extraction
4. Tool Argument Precision
5. Tool Avoidance When Not Needed
6. Disallowed Tool Refusal
7. Ambiguous User Request Clarification
8. Budget-Constrained Completion
9. Graceful Timeout / Failure Recovery
10. Coding-Agent Regression

Each scenario: id, title, goal, input, context, allowed/disallowed tools,
expected behavior (exact | schema | tool_trace | rubric), metrics, tags,
difficulty, budget.

M1 only guarantees **structural validity** and load/validate of these scenario
definitions. Semantic scoring of `expected`/rubrics happens in M2.

## Data Flow

1. `Runner.load_pack` parses and validates YAML/JSON into `ScenarioPack`.
2. Adapter `run(scenario, config)` invokes the agent with the invocation payload.
3. Adapter normalizes the result into `RunArtifact` (output, trajectory,
   cost, status, error, timing).
4. Runner writes artifacts to `.evalforge/runs/<run_id>/`:
   - `run.json` (pack-level index)
   - `artifacts/<scenario_id>.json` (per-scenario RunArtifact)
5. A scenario failure never aborts the pack — each scenario is independent.

## Error Handling

| Failure | Behavior |
|---------|----------|
| Invalid scenario YAML/JSON | `PackParseError` with file + line number |
| Duplicate scenario IDs | `PackParseError` at load |
| Agent timeout | `status="timeout"`, continue pack |
| Agent crash / non-zero exit | `status="error"`, capture stderr, continue |
| Non-JSON stdout with strict_output=true | `status="error"`, continue |
| HTTP connection error / non-200 | `status="error"`, continue |
| Python import error / exception | `status="error"`, capture exception |

## Testing

- **Unit — models:** round-trip serialize/deserialize; required fields;
  defaults.
- **Unit — parser:** valid YAML, valid JSON, duplicate IDs, missing fields,
  bad thresholds, malformed YAML line numbers.
- **Unit — adapters:** each adapter with mock agents covering pass,
  JSON-envelope, raw-text fallback, timeout, crash, non-zero exit, HTTP
  error paths.
- **Integration — runner:** `run_one`, `run_all`, tag filtering, artifact
  save; launch pack loads and validates with zero errors.
- **Coverage gate:** >90% across the suite.

## Out of Scope (M1)

Scoring engine (M2), baselines/comparison (M3), fixture system (M8),
parallel execution (M8), CLI `run` command (M7), LLM-as-judge (M2).