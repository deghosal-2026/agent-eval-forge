# Field Test Plan

## 1. Purpose

Field tests validate that agent-eval-forge works correctly with **real, third-party agent implementations** from the open-source ecosystem — not just the mock agents and stub fixtures used in unit and integration tests.

**What field tests validate that unit/integration tests cannot:**

| Dimension | Unit/Integration | Field |
|---|---|---|
| Agent correctness | Mock agents return known envelopes | Real agents produce real trajectories, outputs, error modes |
| Adapter robustness | Stub frameworks with perfect inputs | Real LangGraph/PydanticAI graphs with varied topologies |
| Dependency compatibility | Isolated `pytest` environment | Real `pip install` / `uv add` across package versions |
| Framework version drift | Locked test dependencies | `main` branch HEAD of real agent repos |
| Trajectory extraction | Synthetic message structures | Framework-native message graphs with edge cases |
| Cost/timing realism | Hardcoded token counts | Real LLM calls (when cost budget allows) |
| CI integration | Single-job test suite | Multi-job matrix over agents with caching |
| Regression detection | Known-good baselines | Per-commit field-test pass/fail deltas |

Field tests are the **final gate** before a release: if an agent that worked last week fails this week, the change is either a breaking regression (block release) or an upstream agent change (document and adapt).

## 2. Agent Selection Criteria

### Qualification Criteria

An agent qualifies for field testing when it meets **all** of:

1. **Production quality** — the repo has >= 100 GitHub stars, or is maintained by a recognized organization, or has >= 2 contributors with commits in the last 90 days.
2. **Framework-aligned** — the agent uses one of eval-forge's supported adapter types: LangGraph (`create_react_agent`), PydanticAI, HTTP, or subprocess.
3. **Runnable offline** — the agent can be configured with either a local model (Ollama, MLX) or a provided API key via environment variable. Agents that require exclusive or proprietary hardware are excluded.
4. **Open source license** — MIT, Apache 2.0, BSD-3, or other permissive license. GPL/LGPL agents may be included if they do not contaminate eval-forge's license.
5. **Tool-using** — the agent must use tools/functions. Pure chat agents (no tool calls) are out of scope for field tests because they produce no trajectory to validate.

### Minimum Complexity Bar

| Property | Minimum |
|---|---|
| Tools defined | >= 2 tools |
| Graph nodes (LangGraph) | >= 3 nodes (including entry + exit) |
| Message types exercised | >= 2 (user + tool, or user + assistant) |
| Dependency count | >= 1 framework dependency beyond the standard library |

### Sourcing Candidates

Candidate agents are sourced from:

- **GitHub topic search:** `topic:langgraph-agent`, `topic:pydantic-ai`, `topic:ai-agent`
- **Awesome lists:** `awesome-langgraph`, `awesome-pydantic-ai`, `awesome-ai-agents`
- **Community nominations:** filed as GitHub issues in eval-forge with the `field-test-candidate` label
- **Manual additions:** documented in `field/AGENTS.md` with rationale

Each candidate is evaluated via a checklist (see `field/CHECKLIST.md` template in the field harness) before inclusion.

## 3. Sourcing Strategy

### Strategy: Git Clone + Config-Driven

Field tests **git clone** each agent repository at a pinned commit (not latest `HEAD`) into a local cache. This gives deterministic results across re-runs while keeping the workflow simple.

| Approach | Chosen? | Rationale |
|---|---|---|
| **Git clone** | Yes | Deterministic, no registry dependency, easy local reproduction |
| Git submodule | No | Submodules pollute the eval-forge repo; updating 20+ submodules per field test cycle is noisy |
| Vendored copy | No | Bloats the repo; license attribution tracking is manual; no upstream update story |
| Registry/pip | No | Most agents are not published to PyPI; pinning is harder without a commit SHA |

### Cache directory layout

Agents are cached under the field test harness root at:

```
field/
├── agents/                     # git clones live here
│   ├── langgraph-simple-rag/   # repo dir = slug from field.json
│   │   ├── .git/
│   │   └── ...
│   ├── pydantic-ai-web-scraper/
│   └── ...
├── scenarios/                  # scenario packs per agent category
├── field.json                  # per-agent config (see §4)
└── conftest.py                 # shared pytest fixtures
```

### Cache Management

- **First run:** `field/setup.sh` is invoked; it reads `field.json` entries, checks if the target directory exists, and clones missing repos.
- **Re-clone policy:** `field/run.sh --refresh` deletes the clone and re-clones. Default is to keep the existing clone.
- **Stale detection:** A `field/COMMIT_SHA.txt` is written after each successful run. If the SHA changes vs `field.json[].commit`, the next run warns and defaults to the pinned SHA unless `--update-pins` is passed.
- **Disk limit:** The total cache is capped at 2 GB. If setup exceeds this, the oldest last-used clone is evicted.

## 4. `field.json` Schema

Every agent in the field test suite has a corresponding `field.json` file that describes how to source, build, and run it.

### Full JSON Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://evalforge.dev/schemas/field-v1.json",
  "title": "Field Agent Configuration",
  "description": "Describes a single agent for field-test execution.",
  "type": "object",
  "required": [
    "agent_id", "name", "repo", "commit", "adapter_type",
    "scenario_packs", "acceptance"
  ],
  "properties": {
    "agent_id": {
      "type": "string",
      "pattern": "^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$",
      "description": "Unique slug used for cache directory and test IDs."
    },
    "name": {
      "type": "string",
      "description": "Human-readable agent name."
    },
    "repo": {
      "type": "string",
      "format": "uri",
      "pattern": "^https://github\\.com/.+/.+$",
      "description": "Git clone URL."
    },
    "commit": {
      "type": "string",
      "pattern": "^[a-f0-9]{40}$",
      "description": "Pinned commit SHA for deterministic builds."
    },
    "branch": {
      "type": "string",
      "default": "main",
      "description": "Branch to clone."
    },
    "subdirectory": {
      "type": "string",
      "description": "Subdirectory within the repo that contains the agent entry point, if not the repo root."
    },
    "adapter_type": {
      "type": "string",
      "enum": ["langgraph", "pydantic-ai", "http", "subprocess", "python"],
      "description": "EvalForge adapter type used to invoke this agent."
    },
    "adapter_config": {
      "type": "object",
      "description": "Adapter-specific configuration (command, module, function, URL, etc.).",
      "properties": {
        "module": { "type": "string" },
        "function": { "type": "string", "default": "build_agent" },
        "command": { "type": "string" },
        "url": { "type": "string", "format": "uri" },
        "timeout_seconds": { "type": "integer", "default": 120, "minimum": 10 }
      },
      "minProperties": 1
    },
    "setup_commands": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Shell commands to run after clone, before testing (e.g., 'uv sync', 'pip install -e .')."
    },
    "env": {
      "type": "object",
      "additionalProperties": { "type": "string" },
      "description": "Environment variables to set during field test. Values may reference $OTHER_VAR for substitution. Secret values are injected at CI runtime, never stored here."
    },
    "scenario_packs": {
      "type": "array",
      "items": { "type": "string", "pattern": "\\.yaml$" },
      "minItems": 1,
      "description": "Relative paths (from field/ directory) to scenario pack YAML files to run against this agent."
    },
    "acceptance": {
      "type": "object",
      "required": ["minimum_pass_rate", "required_metrics"],
      "properties": {
        "minimum_pass_rate": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "Minimum fraction of scenarios that must pass (pass_rate = scenarios_passed / total_scenarios)."
        },
        "required_metrics": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Metric names that MUST pass for the field test to be considered passing. If any required_metric fails, the field test fails regardless of pass rate."
        },
        "allow_zero_disallowed_failures": {
          "type": "boolean",
          "default": false,
          "description": "If true, a zero_disallowed_actions failure is treated as a warning, not a hard failure (for agents that intentionally demonstrate forbidden tool calls)."
        },
        "max_consecutive_failures": {
          "type": "integer",
          "default": 5,
          "description": "Maximum consecutive field-test failures before the agent is automatically quarantined and excluded from the CI matrix."
        }
      }
    },
    "cost_budget": {
      "type": "object",
      "properties": {
        "max_cost_usd_per_run": {
          "type": "number",
          "minimum": 0.0,
          "description": "Maximum total LLM API cost in USD for one full field-test run against this agent. Default 0 (no LLM calls are expected)."
        },
        "model": {
          "type": "string",
          "description": "Expected model identifier used by this agent (for cost tracking)."
        }
      }
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Tags for filtering which agents to run (e.g., ['langgraph', 'rag', 'fast'])."
    },
    "flake_config": {
      "type": "object",
      "properties": {
        "max_retries": { "type": "integer", "default": 2, "minimum": 0 },
        "retry_delay_seconds": { "type": "integer", "default": 5, "minimum": 0 },
        "flake_rate_threshold": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "If an agent's historical flake rate exceeds this, it is quarantined."
        }
      }
    },
    "quarantined": {
      "type": "boolean",
      "default": false,
      "description": "If true, this agent is skipped during field test runs. Used for agents that are broken due to upstream changes or persistent infra issues."
    }
  },
  "allOf": [
    {
      "if": { "properties": { "adapter_type": { "const": "subprocess" } } },
      "then": { "required": ["adapter_config"] },
      "else": { "required": ["adapter_config"] }
    }
  ]
}
```

### Example `field.json`

```json
{
  "agent_id": "langgraph-simple-rag",
  "name": "LangGraph Simple RAG Agent",
  "repo": "https://github.com/example/langgraph-simple-rag",
  "commit": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "adapter_type": "langgraph",
  "adapter_config": {
    "module": "agent.graph",
    "function": "build_agent",
    "timeout_seconds": 60
  },
  "setup_commands": [
    "uv sync --extra dev"
  ],
  "env": {
    "OPENAI_API_KEY": "$OPENAI_API_KEY"
  },
  "scenario_packs": [
    "scenarios/retrieval.yaml",
    "scenarios/safety.yaml"
  ],
  "acceptance": {
    "minimum_pass_rate": 0.8,
    "required_metrics": ["zero_disallowed_actions", "tool_correctness"]
  },
  "cost_budget": {
    "max_cost_usd_per_run": 0.50,
    "model": "gpt-4o-mini"
  },
  "tags": ["langgraph", "rag"],
  "flake_config": {
    "max_retries": 2,
    "flake_rate_threshold": 0.15
  }
}
```

## 5. Scenario Pack Design

Scenario packs are designed **per agent category** to exercise the adapter's specific strengths. All packs live under `field/scenarios/`.

### Category: LangGraph Agents

Scenario pack: `field/scenarios/langgraph-core.yaml`

| Scenario ID | Goal | Key Metrics | Rationale |
|---|---|---|---|
| `lg-func-call-seq` | Agent calls 2+ tools in sequence | `tool_correctness`, `step_efficiency` | Validates multi-step trajectory extraction |
| `lg-func-conditional` | Agent conditionally branches based on tool output | `tool_called`, `synthesis_quality` | Exercises conditional graph edges |
| `lg-no-tool-needed` | Agent responds without calling any tool | `tool_correctness` (no disallowed), `task_completion` | Tests final response extraction |
| `lg-tool-error-recovery` | Tool returns error; agent retries or reports | `retry_discipline`, `recovery_quality` | Tests error-path trajectory extraction |
| `lg-multi-turn` | Agent asks clarifying question, receives answer, then proceeds | `clarification_quality`, `tool_called` | Exercises multi-turn message history |

### Category: PydanticAI Agents

Scenario pack: `field/scenarios/pydantic-ai-core.yaml`

| Scenario ID | Goal | Key Metrics | Rationale |
|---|---|---|---|
| `pai-structured-output` | Agent returns typed structured output | `schema_validity`, `field_correctness` | Validates `result.data` extraction |
| `pai-tool-call` | Agent calls a tool and returns result | `tool_correctness`, `argument_correctness` | Exercises `ToolCallPart`/`ToolReturnPart` extraction |
| `pai-retry-tool` | Tool retry triggered via `RetryToolPart` | `retry_discipline` | Exercises retry trajectory path |
| `pai-system-prompt` | Agent follows a detailed system prompt | `task_completion`, `output_correctness` | Tests system prompt injection path |
| `pai-streaming-fallback` | Agent uses streaming; adapter falls back to sync | `task_completion` | Edge case: streaming agents produce different internal state |

### Category: HTTP Agents

Scenario pack: `field/scenarios/http-core.yaml`

| Scenario ID | Goal | Key Metrics | Rationale |
|---|---|---|---|
| `http-simple-query` | Send input, receive JSON response | `task_completion`, `output_correctness` | Validates basic HTTP round-trip |
| `http-tool-trace` | Agent returns trajectory in envelope | `tool_correctness`, `step_efficiency` | Tests envelope parsing on HTTP response |
| `http-connection-error` | Server returns 500 or times out | `status == "error"` | Validates error normalization |
| `http-auth-header` | Agent requires API key via header | `task_completion` | Tests custom header injection |

### Category: Subprocess Agents

Scenario pack: `field/scenarios/subprocess-core.yaml`

| Scenario ID | Goal | Key Metrics | Rationale |
|---|---|---|---|
| `sub-simple-stdin` | Agent reads input from stdin, writes output | `task_completion` | Validates stdin/stdout contract |
| `sub-json-envelope` | Agent writes JSON envelope | `tool_correctness`, `step_efficiency` | Exercises envelope parsing |
| `sub-nonzero-exit` | Agent exits non-zero with error on stderr | `status == "error"`, error message captured | Validates crash normalization |
| `sub-timeout` | Agent hangs beyond timeout | `status == "timeout"` | Validates timeout enforcement |

### Shared Scenarios (all categories)

`field/scenarios/shared-safety.yaml` runs against every agent:

| Scenario ID | Goal |
|---|---|
| `safety-disallowed-tool` | Agent must refuse to call a disallowed tool |
| `safety-boundary` | Agent must not exceed its allowed scope |

## 6. Harness Architecture

### Directory Structure

```
field/
├── conftest.py                 # Shared fixtures, markers, plugin setup
├── setup.sh                    # Clone/pull agents, install deps
├── run.sh                      # Entry point for CI: clone + pytest
├── quarantine.sh               # Move failed agents in/out of quarantine
├── field.json                  # (Directory) per-agent field.json files
├── scenarios/                  # Scenario packs
│   ├── langgraph-core.yaml
│   ├── pydantic-ai-core.yaml
│   ├── http-core.yaml
│   ├── subprocess-core.yaml
│   └── shared-safety.yaml
├── results/                    # Timestamped run outputs (gitignored)
│   └── 2026-08-01T12-00-00/
└── AGENTS.md                   # Documentation of all field-tested agents
```

### Pytest Design

#### Markers

Registered in `field/conftest.py`:

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "field: mark test as a field test",
    "field_agent(agent_id): identify which agent a test runs against",
    "field_category(category): langgraph | pydantic-ai | http | subprocess",
    "field_expensive: mark tests that use paid LLM APIs (cost gate)",
]
```

#### Parametrized Pattern

Each test function is parametrized over `(scenario, field_config)` using the existing `pytest_generate_tests` hook pattern from the evalforge plugin, but extended to load agent configs from `field.json` files:

```python
# field/conftest.py

def pytest_addoption(parser):
    parser.addoption("--field-agents", type=str, default=None,
                     help="Comma-separated agent_ids to run")
    parser.addoption("--field-category", type=str, default=None,
                     help="Filter by agent category")
    parser.addoption("--field-cost-budget", type=float, default=0.0,
                     help="Max total API cost in USD for this run")
    parser.addoption("--field-refresh", action="store_true",
                     help="Re-clone agent repos")
    parser.addoption("--field-quarantine", action="store_true",
                     help="Run quarantined agents too")


def pytest_configure(config):
    config.addinivalue_line("markers", "field(...)")
    config.addinivalue_line("markers", "field_agent(agent_id)")
    config.addinivalue_line("markers", "field_category(category)")
    config.addinivalue_line("markers", "field_expensive")


def pytest_generate_tests(metafunc):
    if "field_scenario" in metafunc.fixturenames:
        agents = load_field_configs(metafunc.config)
        scenarios = load_field_scenarios(agents)
        ids = [f"{s.agent_id}::{s.scenario_id}" for s in scenarios]
        metafunc.parametrize("field_scenario", scenarios, ids=ids)
```

#### Fixture: `field_scenario`

Named tuple or dataclass:

```python
@dataclass
class FieldScenario:
    agent_id: str
    field_config: dict       # entire field.json for this agent
    scenario: Scenario       # the evalforge Scenario object
    scenario_pack_path: str  # path to the source YAML
```

#### Fixture: `field_agent_adapter`

Builds a fresh adapter per test, applying the `field.json` `adapter_config`:

```python
@pytest.fixture
def field_agent_adapter(field_scenario):
    config = field_scenario.field_config
    adapter_cfg = dict(config["adapter_config"])
    adapter_cfg["run_id"] = f"field-{config['agent_id']}-{generate_run_id()}"
    return create_adapter({"type": config["adapter_type"], **adapter_cfg})
```

#### Test Function Template

```python
@pytest.mark.field
def test_field_agent(field_scenario, field_agent_adapter):
    agent_id = field_scenario.agent_id
    scenario = field_scenario.scenario

    artifact = field_agent_adapter.run(scenario, {"run_id": ...})

    # Validate the agent ran at all
    assert artifact.status in ("completed", "error"), f"Unexpected status: {artifact.status}"

    # If the agent completed, run scoring
    if artifact.status == "completed":
        acceptance = field_scenario.field_config["acceptance"]
        pack = load_pack(field_scenario.scenario_pack_path)
        engine = ScoringEngine()
        run_score = engine.score_run(pack, [artifact], judge=get_judge(config))

        # Assert pass rate
        passed = sum(1 for s in run_score.scenario_scores.values() if s.overall == "passed")
        total = len(run_score.scenario_scores)
        pass_rate = passed / total if total else 0.0
        assert pass_rate >= acceptance["minimum_pass_rate"], (
            f"Pass rate {pass_rate:.2f} < {acceptance['minimum_pass_rate']: .2f}"
        )

        # Assert required metrics
        for metric_name in acceptance.get("required_metrics", []):
            for scenario_score in run_score.scenario_scores.values():
                if metric_name in scenario_score.results:
                    assert scenario_score.results[metric_name].passed, (
                        f"Required metric {metric_name} failed"
                    )
```

### CI Job Design

```yaml
# .github/workflows/field-tests.yml
name: Field Tests

on:
  schedule:
    - cron: "0 6 * * 1"      # weekly on Monday
  workflow_dispatch:
    inputs:
      agents:
        description: "Comma-separated agent IDs (all if empty)"
      refresh:
        description: "Re-clone agent repos"
        type: boolean

jobs:
  setup:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.gen-matrix.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - id: gen-matrix
        run: |
          python field/generate_matrix.py > matrix.json
          echo "matrix=$(cat matrix.json)" >> $GITHUB_OUTPUT

  field-test:
    needs: setup
    runs-on: ubuntu-latest
    strategy:
      matrix:
        agent: ${{ fromJson(needs.setup.outputs.matrix) }}
      fail-fast: false    # one agent failure should not cancel others
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra dev --extra judge --extra langgraph --extra pydanticai
      - run: bash field/setup.sh --agent ${{ matrix.agent.agent_id }}
      - name: Run field tests
        run: >
          uv run pytest field/
          --field-agents ${{ matrix.agent.agent_id }}
          --field-cost-budget ${{ matrix.agent.cost_budget }}
          --tb=short -q
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - name: Upload results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: field-results-${{ matrix.agent.agent_id }}
          path: field/results/

  summary:
    needs: field-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python field/summarize.py > $GITHUB_STEP_SUMMARY
```

**Key design decisions:**
- `fail-fast: false` — one agent's field test failure must not cancel others.
- Weekly schedule + manual trigger (not PR-triggered) — field tests are slower and cost money.
- Each agent runs as a separate matrix job for parallelism and clear failure attribution.
- Secrets are injected at CI runtime via GitHub Actions secrets, never stored in `field.json`.

### Caching Strategy

| Cache | Key | Storage | Policy |
|---|---|---|---|
| Agent repos | Agent commit SHA | `field/agents/` | Evicted by LRU at 2 GB; refreshed on `--field-refresh` |
| Python dependencies | `uv.lock` hash | GitHub Actions cache | Standard `setup-uv` cache |
| LLM judge responses | Scenario+model hash | `field/.judge_cache/` | Evicted after 7 days; skipped when `--no-cache` |

## 7. Acceptance Criteria

### Per-Agent-Type Acceptance

| Agent Type | Minimum Pass Rate | Required Metrics (must all pass) | Additional Conditions |
|---|---|---|---|
| LangGraph | 80% (4 of 5 `lg-*` scenarios) | `zero_disallowed_actions`, `tool_correctness` | Trajectory must contain >= 2 steps for multi-tool scenarios |
| PydanticAI | 80% (4 of 5 `pai-*` scenarios) | `schema_validity`, `field_correctness` | Structured output must match declared schema |
| HTTP | 80% (3 of 4 `http-*` scenarios) | `task_completion` | Response must be valid JSON when JSON is expected |
| Subprocess | 75% (3 of 4 `sub-*` scenarios) | `task_completion` | Non-zero exit is acceptable if `error` message is informative |

### Global Acceptance (all agents)

1. **Safety gate:** No agent may fail `shared-safety.yaml` scenarios on `zero_disallowed_actions`. A safety failure is an automatic field-test **FAIL** for that agent, regardless of pass rate.
2. **No crash cascade:** A single agent crash (exit code non-zero / timeout) must not abort the field test matrix. Each agent is independent.
3. **Report completeness:** Every field test run produces a summary showing per-agent pass/fail, pass rate, and any flake retries consumed.

### Quarantine Policy

An agent is moved to quarantine (`"quarantined": true` in its `field.json`) when:

1. **3 consecutive runs** fail to meet acceptance criteria.
2. **Flake rate exceeds 15%** over the last 10 runs.
3. **API cost exceeds budget** by more than 2x for 2 consecutive runs.

Quarantined agents are excluded from CI but remain in the repo with their `field.json` updated. A GitHub issue is auto-filed when an agent is quarantined.

## 8. Failure Taxonomy

Every field test failure is classified into exactly one category:

### Class A: Dependency Failure

The agent's dependencies cannot be installed or are incompatible with the test environment.

| Pattern | Detection | Action |
|---|---|---|
| `uv sync` / `pip install` fails | Setup script exit code != 0 | Skip test, report as setup failure |
| ImportError at test time | `pytest` catches import exception | `pytest.skip("dependency not available")` |
| Incompatible Python version | Python version check | `pytest.skip("requires Python 3.12+")` |

**Not a bug in eval-forge.** The agent repo may have drifted. File is not quarantined for dependency failures alone (up to 3 consecutive runs).

### Class B: Agent Error

The agent ran but produced incorrect or incomplete output.

| Pattern | Detection | Action |
|---|---|---|
| Agent returns status=error | `artifact.status == "error"` | Record metric failure |
| Agent times out | `artifact.status == "timeout"` | Record metric failure |
| Trajectory is empty when tools are required | `len(artifact.trajectory) == 0` | Record metric failure |
| Output is gibberish/non-responsive | Judge scorer returns low score | Record metric failure |
| Agent calls disallowed tool | `zero_disallowed_actions` fails | Safety failure → quarantine |

**May be a bug in eval-forge or in the agent.** Investigate. If the agent changed upstream, document and update the pinned commit.

### Class C: EvalForge Bug

The agent ran successfully but eval-forge's scoring or adapter produced an incorrect result.

| Pattern | Detection | Action |
|---|---|---|
| Adapter raises unexpected exception | Test traceback in logs | File eval-forge issue |
| Scoring engine raises for valid metric | Engine catches → `ScoreResult(error=...)` | File eval-forge issue |
| Trajectory extraction misses steps | Manual inspection of artifact | File eval-forge issue |
| Judge client returns malformed verdict | `JudgeError` logged | File eval-forge issue |

**Always a bug in eval-forge.** Block release if on `main`.

### Class D: Flake

The test fails non-deterministically — passes on retry with no code change.

| Pattern | Detection | Action |
|---|---|---|
| Passes on retry with same commit | Retry comparison | Increment flake counter |
| Fails intermittently across CI runs | Cross-run comparison | Increment flake counter |
| LLM judge returns different verdicts | `temperature=0` but model still non-deterministic | Increment flake counter |

**Not a bug in eval-forge or the agent.** Tracked; if flake rate exceeds threshold, the agent is quarantined.

### Classification Flow

```
Test fails
  ├─ Setup failed? ──────────────→ Class A (Dependency)
  ├─ Parser/validator exception? ─→ Class C (EvalForge bug)
  ├─ Retry passes? ───────────────→ Class D (Flake)
  ├─ Safety metric failed? ───────→ Class B (Agent error, quarantine)
  ├─ Agent status=error/timeout? ─→ Class B (Agent error)
  └─ Scoring failed? ────────────→ Class B or C (inspect)
```

## 9. Flake Budget & Retry Policy

### Per-Agent Timeouts

| Agent Type | Per-Scenario Timeout | Per-Agent Total |
|---|---|---|
| LangGraph | 120 s | 600 s (5 scenarios × 120 s) |
| PydanticAI | 60 s | 300 s |
| HTTP | 30 s | 120 s |
| Subprocess | 60 s | 240 s |

If a single scenario exceeds its timeout, it is recorded as `status="timeout"` and the agent continues to the next scenario.

### Retry Policy

1. **Automatic retry:** Any field test failure (except safety failures and setup failures) is automatically retried once.
2. **Second retry:** If the first retry also fails, the test is retried a second time with extended per-scenario timeout (1.5x).
3. **Max retries:** 2 per agent per run.
4. **Retry delay:** 5 seconds between retries (configurable via `flake_config.retry_delay_seconds`).
5. **Safety failures are NOT retried.** A safety failure is always recorded as a failure.

### Flake Rate Tracking

Flake rate is computed over the last 10 runs:

```
flake_rate = flaky_failures / total_failures
```

Where:
- `flaky_failures` = failures that passed on retry within the same run.
- `total_failures` = all non-setup failures.

If `flake_rate > flake_rate_threshold` (default 0.15), the agent is automatically quarantined.

Flake tracking is stored in `field/flake_tracker.json`:

```json
{
  "langgraph-simple-rag": {
    "total_runs": 10,
    "total_failures": 4,
    "flaky_failures": 1,
    "flake_rate": 0.25,
    "quarantined": true,
    "last_run": "2026-08-01T12:00:00Z"
  }
}
```

## 10. Cost Budget

### API Cost Constraints

| Tier | Budget per Run | Budget per Month | Agents |
|---|---|---|---|
| Free (no LLM calls) | $0.00 | $0.00 | Pure tool-calling agents (Ollama, mock judge) |
| Economy | $0.50 | $5.00 | Agents using `gpt-4o-mini`, `claude-3-haiku`, or equivalent |
| Standard | $2.00 | $20.00 | Agents using `gpt-4o`, `claude-3.5-sonnet`, or equivalent |
| Premium | $5.00 | $50.00 | Agents using `gpt-4.1`, `claude-3.5-opus`, or complex multi-step scenarios |

### Cost Tracking

1. **Per-agent budget** is set in `field.json` under `cost_budget.max_cost_usd_per_run`.
2. **CI enforces:** before running a field test, the harness checks `cumulative_cost + agent_budget <= total_monthly_budget`. If exceeded, the test is skipped with a warning.
3. **Realtime tracking:** the `run.sh` script maintains a `field/cost_tracker.json`:

   ```json
   {
     "month": "2026-08",
     "total_spent_usd": 12.34,
     "agents": {
       "langgraph-simple-rag": {
         "model": "gpt-4o-mini",
         "total_cost_usd": 0.42,
         "run_count": 3
       }
     }
   }
   ```

4. **LLM judge calls** are also tracked. Judge calls use the `--evalforge-judge` setting (default `mock` for field tests). If a real judge is required, that cost is charged to the agent's budget.

### Budget Enforcement

| Condition | Action |
|---|---|
| Agent exceeds per-run budget | Test is skipped; agent marked as `cost_overrun` in summary |
| Month budget exceeded | All remaining paid-agent tests are skipped |
| Agent has no `cost_budget` set | Agent is treated as free tier (max $0.00 / run) |

### Cost Optimization

- **Mock judge is the default for field tests.** Real LLM judges are only used when explicitly configured and cost-budgeted.
- **Scenario packs for field tests avoid expensive LLM-dependent metrics** where possible, preferring deterministic scorers.
- **Cached judge responses** (see §6) are reused within the same run to avoid redundant API calls.

## 11. Implementation Plan

### Phase 1: Scaffold (estimated 2 days)

1. Create `field/` directory with `conftest.py`, `__init__.py`, `setup.sh`, `run.sh`.
2. Implement `load_field_configs()` — discover `field/field.json/*.json` files and validate against the schema.
3. Implement `pytest_generate_tests` hook that parametrizes `(agent, scenario)` pairs.
4. Write `field/scenarios/` — the 5 scenario packs defined in §5.
5. Add `@pytest.mark.field` marker registration in `pyproject.toml`.

### Phase 2: Setup & Cache (estimated 2 days)

6. Implement `field/setup.sh` — clone agents, run `setup_commands`, verify entry points.
7. Implement cache directory with LRU eviction (2 GB cap).
8. Commit one reference agent `field.json` (e.g., `langgraph-simple-rag`) to validate the pipeline end-to-end.

### Phase 3: Scoring & Retry (estimated 2 days)

9. Wire `ScoringEngine` into the test template (§6 pattern).
10. Implement retry logic with configurable max_retries and delay.
11. Implement flake tracker (`field/flake_tracker.json`).
12. Implement failure taxonomy classification in post-test hooks.

### Phase 4: CI Matrix (estimated 2 days)

13. Create `.github/workflows/field-tests.yml` — setup → matrix → per-agent job → summary.
14. Implement `field/generate_matrix.py` — reads `field/field.json/`, excludes quarantined, outputs GitHub Actions matrix.
15. Implement `field/summarize.py` — reads `field/results/`, produces GitHub Actions step summary markdown.
16. Implement `field/quarantine.sh` — auto-quarantine agents exceeding flake rate.

### Phase 5: Cost Tracking (estimated 1 day)

17. Implement `field/cost_tracker.py` — reads API responses, accumulates costs, enforces budgets.
18. Wire cost tracking into the CI pipeline as a pre-test gate.
19. Add `--field-cost-budget` CLI option to `conftest.py`.

### Phase 6: Onboarding (estimated 3 days)

20. Add 5-10 reference agents across all 4 adapter categories.
21. Write `field/AGENTS.md` documenting each agent, its purpose, and its `field.json` location.
22. Run full field test suite, fix any bugs found in the harness.
23. Add `field/test_harness.py` — unit tests for the harness itself (config loading, failure taxonomy, flake tracking).

### Rollout Checklist

- [ ] Phase 1 complete: parametrized tests pass with mock scenario
- [ ] Phase 2 complete: `setup.sh` clones an agent and `pytest` runs against it
- [ ] Phase 3 complete: scoring + retry produce correct pass/fail classification
- [ ] Phase 4 complete: CI matrix runs 3+ agents in parallel
- [ ] Phase 5 complete: cost budget enforcement works (test by setting $0 budget for a known-expensive agent)
- [ ] Phase 6 complete: 5+ agents pass field tests consistently
- [ ] Documentation written (`AGENTS.md`, field test README)
- [ ] Gate added to release checklist: "Run field tests before tagging"