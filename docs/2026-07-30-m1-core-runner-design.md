# M1: Core Runner — Design

**Date:** 2026-07-30
**Status:** Approved (design decisions incorporated)
**Dependencies:** Spec v1.0 (approved), WBS v1.0 (M0 complete)

## Decisions (from design review)

1. **Subprocess I/O contract:** EvalForge passes scenario JSON on stdin; agent
   writes a JSON envelope (`{output, trajectory, cost, status}`) to stdout.
   If stdout is not valid JSON, EvalForge falls back to treating raw text as
   the final output with an empty trajectory. This lets existing CLI agents
   produce valid artifacts without changes while enabling rich trajectories
   for agents that opt in.
2. **Launch pack pulled forward:** All 20 launch scenarios are authored in M1
   (`scenarios/core-launch.yaml`). M4/M5 now cover only mock agents, tests,
   and fixture data.

## Goal

Load scenario packs, invoke agents through adapters, and capture normalized
`RunArtifact`s. This is the execution spine everything else (scoring,
comparison, baselines) builds on.

## Architecture

Single-command flow, library-first:

```
pack YAML/JSON → ScenarioPack → Runner → adapter.run(scenario) → RunArtifact → save to .evalforge/runs/
```

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

### Adapters (`src/evalforge/adapters/`)

- **`base.py`** — `Adapter` ABC with `run(scenario, config) -> RunArtifact`,
  per-scenario timeout enforcement, error capture/normalization. `config`
  carries adapter-specific settings (command, module/function, url,
  timeout_seconds).
- **`subprocess.py`** — stdin JSON in, JSON-envelope parse with raw-text
  fallback; handles timeout (status=`timeout`), crash (status=`error` +
  stderr), non-zero exit.
- **`python_import.py`** — import module, call function
  `run(input, tools, context)`, capture return value and exceptions.
- **`http.py`** — POST scenario JSON, handle connection errors, timeouts,
  non-200 responses.
- **`factory.py`** — resolve adapter from agent config by `type:`.

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

## Data Flow

1. `Runner.load_pack` parses and validates YAML/JSON into `ScenarioPack`.
2. Adapter `run(scenario, config)` invokes the agent with the scenario.
3. Adapter normalizes the result into `RunArtifact` (output, trajectory,
   cost, status, error, timing).
4. Runner writes artifacts to `.evalforge/runs/run-<ts>-<id>.json`.
5. A scenario failure never aborts the pack — each scenario is independent.

## Error Handling

| Failure | Behavior |
|---------|----------|
| Invalid scenario YAML/JSON | `PackParseError` with file + line number |
| Duplicate scenario IDs | `PackParseError` at load |
| Agent timeout | `status="timeout"`, continue pack |
| Agent crash / non-zero exit | `status="error"`, capture stderr, continue |
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
