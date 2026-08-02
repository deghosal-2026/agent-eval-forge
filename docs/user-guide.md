# EvalForge User Guide

> **`pytest` for agents.** A framework-agnostic evaluation harness that catches
> regressions before you ship — correctness, tool discipline, safety boundaries,
> cost, and latency.

---

## The Question EvalForge Answers

You shipped a prompt change. The demo looks great. Three days later, a customer
hits a regression the demo never covered. Sound familiar?

Agent teams change prompts, models, tools, and orchestration logic constantly —
but most still judge progress by eyeballing a handful of examples. That works
for demos. It fails for production. The final answer isn't the only thing that
matters: the path taken, the tools selected, the arguments passed, the cost
incurred, and the safety boundaries respected all matter.

**EvalForge exists to make agent improvement measurable, repeatable, and
comparable across versions.** It turns release decisions from anecdotes into
evidence.

> *"Did the agent actually get better, or did it just change?"*

### What it is — and isn't

**Is:** A release-discipline product. Local-first, CI-second. Strong default
rubrics out of the box, all overridable. Built for one job: deciding whether an
agent change is safe to ship.

**Is not:** A generic LLM eval framework, an auto-prompt optimizer, a hosted
observability platform, or a benchmark leaderboard.

### Who it's for

1. **Solo OSS builders** shipping tool-using agents who need release confidence
2. **Small teams** with internal agents who need repeatable baselines
3. **Platform teams** supporting many agent repos who need shared governance

### The day-one win

Catch one regression before merge. That's the smallest meaningful adoption
outcome.

---

## Table of Contents

| # | Section | If you want to… |
|---|---|---|
| 1 | [Installation](#1-installation) | Get it running |
| 2 | [Quick Start](#2-quick-start--first-eval-in-5-minutes) | Your first eval in 5 minutes |
| 3 | [Core Concepts](#3-core-concepts) | Understand the mental model |
| 4 | [Writing Scenarios](#4-writing-effective-scenarios) | Author test cases |
| 5 | [Running Evaluations](#5-running-evaluations) | Run, filter, parallelize |
| 6 | [Understanding Results](#6-understanding-results) | Read scores, exit codes, artifacts |
| 7 | [CI Integration](#7-ci-integration) | Gate releases in pipelines |
| 8 | [Custom Adapters](#8-custom-adapters) | Support a new agent runtime |
| 9 | [Custom Scorers](#9-custom-scorers) | Add a metric |
| 10 | [Gotchas](#10-gotchas) | Avoid pain we already hit |
| 11 | [Real-World Workflow](#11-real-world-workflow) | See the full lifecycle |
| 12 | [Configuration Reference](#12-configuration-reference) | Tune defaults |
| 13 | [Command Reference](#13-command-reference) | Look up a command |
| 14 | [Where to Go Next](#14-where-to-go-next) | Keep reading |

---

## 1. Installation

```bash
pip install agent-eval-forge
```

With framework adapters:

```bash
pip install agent-eval-forge[langgraph,pydanticai]
```

With judge backends:

```bash
pip install agent-eval-forge[judge]    # OpenAI + Anthropic
pip install agent-eval-forge[mlx]      # Apple Silicon local judge
```

Everything:

```bash
pip install agent-eval-forge[langgraph,pydanticai,judge,mlx]
```

Verify:

```bash
$ evalforge version
0.1.0
```

---

## 2. Quick Start — First Eval in 5 Minutes

You'll create three things: a **scenario pack** (test cases), an **agent**
(the thing under test), and a **run command** (the evaluation).

### Step 1 — Write a scenario pack

Create `my-pack.yaml`:

```yaml
pack:
  name: "my-pack"
  version: "1.0.0"
  description: "First eval pack"

scenarios:
  - id: "weather-check"
    title: "Basic weather query"
    goal: "Answer a weather question with one tool call"
    input: "What's the weather in Tokyo?"
    allowed_tools:
      - name: "get_weather"
    expected:
      type: exact
      value: "Sunny, 22C"
    metrics:
      task_completion: {threshold: 1.0}
      tool_correctness: {threshold: 1.0}
    difficulty: easy
    budget: {max_steps: 3, max_tokens: 300}
```

### Step 2 — Write a minimal agent

Create `my_agent.py`:

```python
def run(payload: dict) -> dict:
    user = payload.get("input", "")
    tools = payload.get("allowed_tools", [])
    tool_name = tools[0]["name"] if tools else "echo"

    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "Sunny, 22C", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": tool_name, "args": {"query": user}},
                {"type": "tool_result", "tool": tool_name, "result": "Sunny, 22C"},
                {"type": "response", "content": "Sunny, 22C"},
            ]
        },
        "cost": {
            "input_tokens": 10, "output_tokens": 5,
            "total_tokens": 15, "cost_usd": 0.0,
        },
        "error": None,
    }
```

This is the entire agent contract: receive a payload dict, return a run
envelope dict. No framework dependencies needed.

### Step 3 — Run it

```bash
evalforge run --pack my-pack.yaml --agent "python:my_agent:run"
```

You'll see terminal output with per-scenario scores. A green `PASS` means your
agent met every threshold. Artifacts land in `.evalforge/runs/`.

That's the whole loop. Everything else — baselines, judges, CI, custom scorers —
builds on these three primitives.

---

## 3. Core Concepts

### 3.1 Scenario Packs

A scenario pack is a YAML file of one or more test scenarios. Each scenario
defines:

| Field | Purpose |
|---|---|
| `input` | The user message sent to the agent |
| `allowed_tools` | Tools the agent **may** use |
| `disallowed_tools` | Tools the agent **must not** use |
| `expected` | What constitutes a correct answer |
| `metrics` | Scoring rules and thresholds |
| `budget` | Resource limits (steps, tokens, cost) |

EvalForge ships with `scenarios/core-launch.yaml` — 20 production-grade
scenarios across 10 families (retrieval, synthesis, extraction, tool
arguments, refusal, ambiguity, budget, recovery, coding, classification) — and
`scenarios/security-launch.yaml` — 8 security scenarios (prompt injection,
exfiltration, SSRF, sandbox escape).

### 3.2 Expected Answer Types

Four ways to express correctness, cheapest first:

| Type | When | Example | Cost |
|---|---|---|---|
| `exact` | Literal string match | `value: "Tokyo"` | Free |
| `schema` | JSON structure validation | `schema: {type: object, required: [city]}` | Free |
| `tool_trace` | Tool call sequence check | `trace: [{tool: search, args: {q: "Tokyo"}}]` | Free |
| `rubric` | Qualitative criteria for LLM judge | `criteria: ["Answer must cite a source"]` | LLM call |

> **Rule of thumb:** Start with the cheapest type that captures correctness.
> `exact` and `schema` are deterministic and reproducible. Reach for `rubric`
> only when answer quality can't be mechanically verified.

### 3.3 Adapters

Adapters are how EvalForge talks to your agent. All adapters receive the same
**restricted payload** — your agent never sees `expected`, `metrics`, or scoring
thresholds. Those stay inside EvalForge.

| Adapter | Agent spec | Best for |
|---|---|---|
| `subprocess` | `subprocess:./agent.py` | Any language, stdin/stdout contract |
| `python` | `python:my_pkg.agent:run` | Python agents in-process |
| `http` | `http:http://localhost:8000/run` | Agents behind HTTP servers |
| `langgraph` | `langgraph:my_pkg.graph:build_agent` | LangGraph agents |
| `pydantic-ai` | `pydanticai:my_pkg.agent:build_agent` | PydanticAI agents |

### 3.4 Scoring Engine

EvalForge scores in two layers:

1. **Deterministic scorers** — always run, free, reproducible. Tool correctness,
   argument precision, schema validity, budget adherence, safety gates,
   grounding checks. 17 scorers ship built-in.

2. **LLM-as-Judge scorers** — run only when configured. Output correctness,
   task completion, synthesis quality, hallucination detection, refusal
   quality. 11 judge metrics ship built-in.

**Evaluation hierarchy:** Safety failures trump everything. If your agent calls
a disallowed tool, the scenario fails regardless of output quality. Correctness
regressions warn by default but can be promoted to blocking in the pack config.
Efficiency regressions are informational unless explicitly promoted.

### 3.5 Baselines

A baseline is a named snapshot of scores from a known-good agent version:

```bash
# Save after a successful run
evalforge baseline save --name v1.2.3 --run run-20260728-001

# List all
evalforge baseline list

# Describe (tags, annotations, git SHA)
evalforge baseline describe --name v1.2.3

# Compare candidate against baseline
evalforge run --pack my-pack.yaml --agent python:my_agent.py --baseline v1.2.3
```

Comparisons show per-scenario deltas, per-tag regressions, and aggregate score
change. EvalForge prefers explicit golden baselines — not "last run wins" or
"whatever is on main."

---

## 4. Writing Effective Scenarios

### 4.1 Start with deterministic checks

Before reaching for LLM judges, exhaust deterministic metrics:

```yaml
metrics:
  tool_correctness: {threshold: 1.0}     # Right tool called
  argument_correctness: {threshold: 0.9} # Right arguments passed
  step_efficiency: {threshold: 0.8}      # Not too many steps
  zero_disallowed: {threshold: 1.0}      # No forbidden tools
```

Add judge metrics only when correctness can't be mechanically verified. This
keeps evals fast, free, and reproducible.

### 4.2 One thing per scenario

Each scenario should test **one behavior**. Single-purpose scenarios give you
precise regression signals — you know exactly what broke.

**Good:**
```yaml
- id: "refusal-01"
  goal: "Refuse to call a disallowed production tool"
  disallowed_tools:
    - name: "deploy_production"
```

**Bad:**
```yaml
- id: "everything-test"
  goal: "Refuse dangerous tools AND synthesize data AND stay in budget"
```

When the "everything-test" fails, you have to hunt through five failure modes
in one result to figure out what broke.

### 4.3 Budget aggressively

Set budgets tight enough to catch runaway agents:

```yaml
budget:
  max_steps: 5        # Hard limit on trajectory steps
  max_tokens: 500     # Token ceiling
  max_cost_usd: 0.05  # Dollar ceiling per scenario
```

A retrieval scenario shouldn't take 12 steps. If your agent hits the budget,
it's either looping or using the wrong strategy — both worth knowing about.

### 4.4 Disallowed tools for safety

```yaml
disallowed_tools:
  - name: "customer_delete"
  - name: "deploy_production"
  - name: "page_oncall"
```

These produce safety failures (exit code 4) by default — the strictest penalty.
No configuration needed. Safety violations are blocking in all modes.

### 4.5 Tag strategically

Tags group scenarios for parallel runs, CI filtering, and reporting:

```yaml
tags: [retrieval, single-tool, regression]
```

Use a consistent tag vocabulary across packs:
- **Domain**: `retrieval`, `synthesis`, `extraction`, `coding`
- **Complexity**: `single-tool`, `multi-tool`, `budget`
- **Safety**: `refusal`, `boundary`, `prompt-injection`
- **Behavior**: `recovery`, `ambiguity`, `tool-avoidance`

### 4.6 Validate before running

```bash
# Schema-only validation
evalforge validate --pack my-pack.yaml --strict

# Also check agent connectivity
evalforge validate --pack my-pack.yaml --agent python:my_agent.py --pre-flight --strict
```

Catches schema errors, missing fields, invalid metric names, and duplicate IDs
before you waste time running.

---

## 5. Running Evaluations

### 5.1 Basic run

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "python:my_pkg.agent:run"
```

### 5.2 With an LLM judge

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "langgraph:my_pkg.graph:build_agent" \
  --judge openai:gpt-4o-mini
```

Required env var: `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` for Anthropic).

Judge backends:

| Spec | Provider | Key needed |
|---|---|---|
| `openai:gpt-4o-mini` | OpenAI | `OPENAI_API_KEY` |
| `anthropic:claude-3-haiku` | Anthropic | `ANTHROPIC_API_KEY` |
| `ollama:llama3` | Ollama (local) | None |
| `mlx:Qwen3.5-9B` | MLX (Apple Silicon) | None |
| `mock` | MockJudge (harness only) | None |

### 5.3 Filter by tag

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "python:my_agent.py" \
  --tags retrieval      # Only retrieval scenarios
```

### 5.4 Parallel execution

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "python:my_agent.py" \
  --workers 4 \
  --max-outstanding 8
```

`--max-outstanding` caps in-flight scenarios to prevent unbounded memory
growth — useful when scenarios have widely varying runtimes.

### 5.5 Fixtures mode (deterministic, no live dependencies)

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "python:fixtures.echo_agent" \
  --fixtures
```

Replays tool responses from recorded fixture data. Two identical fixture runs
produce identical scores — ideal for CI smoke tests and debugging. Toggle
`--live` for real tool execution.

### 5.6 Sandbox mode

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "subprocess:./agent.py" \
  --sandbox
```

Strips environment variables, isolates filesystem access. Combine with Docker
for network isolation (`--network none`).

### 5.7 CI mode

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "python:my_agent.py" \
  --ci \
  --output-format github-actions
```

`--ci` does three things:
- Suppresses spinners and color output
- Enables structured exit codes (0 = pass, 1+ = failure type)
- Writes to `$GITHUB_STEP_SUMMARY` when available

### 5.8 Programmatic use

```python
from evalforge import runner

result = runner.run(
    pack="scenarios/core-launch.yaml",
    agent="python:my_pkg.agent:run",
    judge="openai:gpt-4o-mini",
    tags=["retrieval"],
)
print(result.summary.passed, result.summary.failed)
```

### 5.9 Pytest plugin

```bash
evalforge test run scenarios/
```

Or mark individual tests:

```python
import pytest

@pytest.mark.evalforge_tags("retrieval")
def test_my_scenario():
    ...
```

---

## 6. Understanding Results

### 6.1 Output formats

| Format | Flag | Use case |
|---|---|---|
| Terminal (default) | — | Local dev, rich tables |
| JSON | `--output-format json` | CI, programmatic consumption |
| Markdown | `--output-format markdown` | PR comments, reports |
| GitHub Actions | `--output-format github-actions` | Workflow annotations |

### 6.2 Exit codes

| Code | Meaning | When |
|---|---|---|
| 0 | All scenarios passed | — |
| 1 | At least one scenario failed | CI mode only |
| 2 | Runtime error | Crash, timeout, adapter failure |
| 3 | Judge error | LLM call failed, no verdict |
| 4 | Safety violation | Disallowed tool called |

> **Gotcha:** Exit code 4 always overrides other failures. If one scenario
> has a safety violation and another has a correctness regression, you get
> exit code 4.
>
> **Gotcha:** In non-CI mode, `evalforge run` **always** exits 0 — even if
> scenarios fail. Use `--ci` for structured exit codes, or check the JSON
> output.

### 6.3 Score thresholds

Each metric has a threshold (0.0–1.0):

| Score relative to threshold | Verdict |
|---|---|
| >= threshold | PASS |
| >= threshold × 0.7 | WARN — close to failure, review needed |
| < threshold × 0.7 | FAIL |

### 6.4 Artifact structure

Every run writes to `.evalforge/runs/<run_id>/`:

```
.evalforge/
  runs/
    run-20260802-143022-a1b2/
      run.json              # Pack-level index
      artifacts/
        weather-check.json  # Per-scenario artifact with full trajectory
  baselines/
    v1.2.3.json
  comparisons/
    v1.3.0-vs-v1.2.3.json
```

Each artifact contains the full agent trajectory (tool calls, arguments,
results, timing), cost breakdown, and per-metric scores with rationales.

### 6.5 Failure taxonomy

EvalForge auto-classifies failures. Access programmatically:

```python
from evalforge.analytics import FailureTaxonomy

report = FailureTaxonomy.analyze(run_score)
# report.failure_breakdown: {"tool_misuse": 3, "hallucination": 1, ...}
# report.recommendations: ["Fix argument parsing in get_weather tool"]
```

Categories include: `safety_violation`, `policy_violation`, `hallucination`,
`tool_error`, `argument_error`, `schema_error`, `budget_exceeded`,
`incorrect_output`, `timeout`, `agent_crash`.

---

## 7. CI Integration

### 7.1 GitHub Actions

```yaml
- name: Run EvalForge
  run: |
    evalforge validate --pack scenarios/core-launch.yaml --strict
    evalforge run \
      --pack scenarios/core-launch.yaml \
      --agent "python:my_pkg.agent:run" \
      --baseline v1.0.0 \
      --judge openai:gpt-4o-mini \
      --ci \
      --output-format github-actions
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

A full workflow template is at `.github/workflows/ci-evalforge.yml` — includes
artifact upload, Docker sandbox, and PR annotations.

### 7.2 GitLab CI

```yaml
evalforge:
  script:
    - evalforge run --pack scenarios/core-launch.yaml --agent python:my_agent.py --ci
  artifacts:
    paths:
      - .evalforge/
```

Full template at `.gitlab-ci.yml`.

### 7.3 Fixture-based smoke test (no API keys)

For fast CI gating without LLM costs:

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent "python:fixtures.echo_agent" \
  --fixtures \
  --ci \
  --output-format github-actions
```

Runs deterministic scorers only — no judge calls, no API keys needed. Ideal for
per-commit smoke checks.

### 7.4 Docker-based sandbox (Linux)

For evaluating untrusted agents with full network isolation:

```bash
docker run --rm --network none ghcr.io/<org>/evalforge:latest \
  bash -lc "evalforge run --pack scenarios/core-launch.yaml --agent subprocess:./agent.py --sandbox --ci"
```

---

## 8. Custom Adapters

When the built-in adapters don't fit, subclass `Adapter`:

```python
from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError, AgentTimeoutError


class MyAdapter(Adapter):
    name = "my-adapter"

    def _invoke(self, payload: dict, config: dict) -> dict:
        # payload contains: input, context, allowed_tools,
        #                  disallowed_tools, budget
        # (expected/metrics are stripped — never forwarded)
        user = payload.get("input", "")

        # Raise AgentTimeoutError on timeout
        # Raise AdapterError for any other failure
        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": f"echo: {user}", "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": None,
        }
```

Register it in the factory (`src/evalforge/adapters/factory.py`), then use:

```bash
evalforge run --agent "my-adapter:my_pkg.agent:run" --pack my-pack.yaml
```

The base class `run()` method handles payload building, timing, error
normalization, and artifact construction — you only implement `_invoke()`.

---

## 9. Custom Scorers

```python
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.base import Scorer
from evalforge.scoring.result import ScoreResult
from evalforge.models.artifact import RunArtifact
from typing import Any


@register_scorer
class ResponseLengthScorer(Scorer):
    name = "response_length"

    def score(self, artifact: RunArtifact, scenario: Any) -> ScoreResult:
        length = len(artifact.output.final or "")
        passed = 10 <= length <= 500
        return ScoreResult(
            metric="response_length",
            score=1.0 if passed else 0.0,
            threshold=0.8,
            passed=passed,
            detail={"length": length, "reason": "outside 10-500 range"},
        )
```

Custom scorers are auto-discovered via entry points. Use the metric name in
scenario packs:

```yaml
metrics:
  response_length: {threshold: 0.8}
```

---

## 10. Gotchas

Lessons from running EvalForge against 20+ real-world agents. These will save
you hours.

### 10.1 Agent must not receive evaluation data

EvalForge strips `expected`, `metrics`, and scoring thresholds from the payload
sent to your agent. If you're writing a custom adapter, make sure you're not
accidentally forwarding the full scenario dict — that defeats the evaluation.

### 10.2 Judge costs add up fast

Even `gpt-4o-mini` at $0.15/1M input tokens burns money across 20 scenarios
with 10 judge metrics each. Use fixtures for fast iteration, save real judges
for CI. The judge cache (24h TTL per hash) helps on re-runs, but the first run
always pays full price.

### 10.3 MockJudge is for harness tests only

`MockJudge` produces a fixed score of 0.85 and is scoped to
`field/test_field_agent.py`. It should never appear in production runs. If you
see `MockJudge` in core tests or CLI paths, something is wrong. Always pass a
real judge:

```bash
# Good
evalforge run ... --judge openai:gpt-4o-mini

# Bad (unless you're in the field harness)
evalforge run ... --judge mock
```

### 10.4 Parallel execution on macOS

`ThreadPoolExecutor` with `python_import` adapters can be brittle on macOS due
to `spawn` semantics. The runner routes through `ProcessPool` for
`python_import` in parallel mode when sandbox is enabled. If you hit
multiprocessing issues, drop to serial (`--workers 1`) for `python_import`
agents, or use the `subprocess` adapter.

### 10.5 Agent import-time side effects

Many real agents do problematic things at module scope that break evaluation:

| Bad pattern | Why it breaks | Fix |
|---|---|---|
| `ChatOpenAI(model="gpt-3.5-turbo")` at import | Hardcoded model 404s on local endpoints | Parameterize model/provider/base_url |
| `FAISS.load_local(...)` at import | Blocks import without data files | Lazy-initialize inside a function |
| `create_async_engine(DATABASE_URL)` at import | Needs a running database | Guard with `if __name__ == "__main__":` |
| Absolute writes to `/root/...` at import | Fails in locked-down sandboxes | Use relative, sandboxed paths |

If you can't fix the agent, use the `subprocess` adapter and `--sandbox` mode.

### 10.6 Don't fight infrastructure-dependent agents

If `import my_agent` needs a running Postgres, Redis, or external API at import
time, that's a property of the agent — not a bug in the runner. Don't waste
hours patching around it. Mark it `quarantined: true` for local tier and run
only in Docker with provisioned infra.

### 10.7 Hardcoded model names vs local endpoints

Agents that hardcode `model="gpt-4"` will 404 against local endpoints (Ollama,
MLX). Set:

```bash
export EVALFORGE_FORCE_MODEL=1
export EVALFORGE_FIELD_MODEL=Qwen3.5-9B-MLX-4bit
```

The adapter monkeypatches `ChatOpenAI.__init__` before the agent module is
imported, injecting the local model when no explicit model is passed. Note:
Pydantic v2 field-default patching does **not** work — the `__init__`
override is the only reliable approach.

### 10.8 Scenario IDs have a restricted character set

Only `[A-Za-z0-9_-]` allowed. Dots, spaces, and special characters in scenario
IDs will be rejected at validation. Use hyphens: `retrieval-01`, not
`retrieval.01` or `retrieval 01`.

### 10.9 Exit code 0 doesn't always mean "pass"

In non-CI mode, `evalforge run` **always** exits 0 — even if scenarios fail. Use
`--ci` for structured exit codes, or check the JSON output:

```bash
# CI mode (exit non-zero on failure)
evalforge run --pack my-pack.yaml --agent python:my_agent.py --ci

# Or inspect JSON
evalforge run --pack my-pack.yaml --agent python:my_agent.py --output-format json | jq '.summary.failed'
```

### 10.10 Baseline comparison: rescore vs snapshot

| Mode | Flag | When to use |
|---|---|---|
| `snapshot` | `--compare-mode snapshot` (default) | Compares saved scores from baseline run. Fast, no new judge calls. CI-friendly. |
| `rescore` | `--compare-mode rescore` | Re-runs judge on both artifacts. Use when the judge model has changed. |

### 10.11 Caches are automatic but clearable

Three caches work silently:

| Cache | Scope | Purpose |
|---|---|---|
| Judge cache | 24h TTL, file-backed | Deduplicates LLM judge calls |
| Run cache | Session-scoped | Avoids re-running unchanged scenarios |
| Schema cache | Pack lifetime | Skips pack validation if hash matches |

Clear when needed:

```bash
evalforge cache clear --cache-type judge
evalforge cache stats
```

### 10.12 Field tests ≠ product runs

The `field/` harness is a smoke rig for third-party repos — adapter wiring,
artifact capture, deterministic scorers. It uses `MockJudge`. Product runs use
real judges and write to `.evalforge/`. Don't treat `field/results/` as product
evidence, and don't let `MockJudge` leak into core paths.

---

## 11. Real-World Workflow

The lifecycle a team goes through, from first eval to continuous gating.

### Phase 1 — Adopt (day 1)

```bash
# 1. Start from the shipped launch pack and trim to your agent
cp scenarios/core-launch.yaml my-agent-pack.yaml
# Edit: remove irrelevant scenarios, add your own

# 2. Wire your agent to an adapter
#    subprocess is easiest — works with any language
evalforge run --pack my-agent-pack.yaml --agent "subprocess:./run.sh"

# 3. Save a golden baseline once it passes
evalforge baseline save --name golden --run run-20260802-143022-a1b2
```

### Phase 2 — Gate (before every merge)

```bash
# 4. Compare against baseline before merging
evalforge run \
  --pack my-agent-pack.yaml \
  --agent "subprocess:./run.sh" \
  --baseline golden \
  --judge openai:gpt-4o-mini \
  --ci

# Exit code ≠ 0 → something regressed. Investigate before merging.
```

### Phase 3 — Continuous (ongoing)

```bash
# 5. Expand the pack as you discover failure modes
#    - Add a scenario for every bug you fix
#    - Tag it so you can run it in isolation
#    - Re-save the baseline after the pack passes

# 6. Wire CI with two tiers:
#    - Fixtures mode for fast per-commit smoke (no API keys)
#    - Full judge run nightly or pre-release
```

---

## 12. Configuration Reference

All values are optional. Create `evalforge.toml` in your project root:

```toml
[judge]
provider = "openai"
model = "gpt-4o-mini"

[output]
dir = ".evalforge"
log_level = "info"      # debug, info, warning, error

[scoring]
strict = false           # treat warnings as failures
compare_mode = "snapshot" # snapshot (default) or rescore
```

CLI flags override config file values. See the shipped `evalforge.toml` for
a commented example.

---

## 13. Command Reference

| Command | Purpose |
|---|---|
| `evalforge run` | Run a scenario pack against an agent |
| `evalforge validate` | Validate packs, agents, baselines |
| `evalforge compare` | Compare candidate vs baseline |
| `evalforge baseline save` | Save run results as a named baseline |
| `evalforge baseline list` | List all baselines |
| `evalforge baseline describe` | Show baseline metadata, tags, annotations |
| `evalforge baseline tag` | Add a tag to a baseline |
| `evalforge baseline annotate` | Add a note to a baseline |
| `evalforge baseline delete` | Remove a baseline |
| `evalforge cache clear` | Clear caches (`--cache-type judge\|run\|schema`) |
| `evalforge cache stats` | Show cache hits and estimated savings |
| `evalforge init` | Scaffold a new scenario pack |
| `evalforge plugins list` | List registered plugins (scorers, adapters) |
| `evalforge benchmark import` | Import external benchmarks (SWE-bench, WebArena) |
| `evalforge test run` | Run scenarios via pytest plugin |
| `evalforge version` | Print installed version |

---

## 14. Where to Go Next

| Topic | Document |
|---|---|
| Scenario authoring — full metric catalog, pack anatomy | `docs/scenarios.md` |
| Scoring deep dive — judge config, custom scorers, failure taxonomy | `docs/scoring.md` |
| LangGraph adapter | `docs/adapters/langgraph.md` |
| PydanticAI adapter | `docs/adapters/pydantic-ai.md` |
| Custom adapters | `docs/adapters/custom.md` |
| External benchmarks (SWE-bench, WebArena) | `docs/adapters/benchmarks.md` |
| CI setup | `docs/ci.md` |
| Security model | `docs/security-review.md` |
| Real-world integration and design lessons | `docs/hard-won-lessons.md` |
| Field test reports | `docs/field-test-report-*.md` |
