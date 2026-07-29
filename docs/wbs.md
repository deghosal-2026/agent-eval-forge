# Agent Eval Forge — Work Breakdown Structure

**Status:** Approved  
**Date:** 2026-07-28  
**Dependencies:** PRD v1.0 (approved), Spec v1.0 (approved)

## Milestone Overview

| Milestone | Scope | Target |
|-----------|-------|--------|
| M0: Scaffold | Repo, config, CI, package structure | Week 2 (Jul 28 - Aug 3) |
| M1: Core Runner | Scenario loading, agent invocation, artifact capture | Week 3 (Aug 4-10) |
| M2: Scoring Engine | Deterministic scorers, LLM-as-judge, hybrid scoring | Week 3 (Aug 4-10) |
| M3: Comparison & Baselines | Baseline save/load, comparison engine, reporting | Week 3 (Aug 4-10) |
| M4: Launch Scenarios 1-5 | Retrieval, synthesis, extraction, tool args, tool avoidance | Week 3 (Aug 4-10) |
| M5: Launch Scenarios 6-10 | Refusal, ambiguity, budget, recovery, coding | Week 3 (Aug 4-10) |
| M6: Framework Adapters | LangGraph adapter, PydanticAI adapter, adapter contract | Week 4 (Aug 11-17) |
| M7: CLI & pytest | CLI surface, pytest plugin, output formats | Week 4 (Aug 11-17) |
| M8: CI & Polish | CI integration, fixtures, caching, parallel execution, security | Week 4 (Aug 11-17) |
| M9: OSS Readiness | OpenSSF badge, docs, LICENSE, README, community files | Week 4 (Aug 11-17) |
| M10: Ship v0.1 | Final integration tests, GitHub release, PyPI | Week 4 (Aug 11-17) |
| M11: OSS Cleanup & Launch | Squash history, public visibility, launch article, community | Week 4 (Aug 11-17) |

---

## M0: Scaffold

**Goal:** Usable project skeleton with CI, linting, testing, and package structure.

### Checklist

- [ ] Initialize Python package structure (`agent-eval-forge/` with `src/evalforge/`) → [#13](https://github.com/deghosal-2026/agent-eval-forge/issues/13)
- [ ] Configure `pyproject.toml` with dependencies and entry points → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
- [ ] Set up `uv` or `pip` for dependency management → [#15](https://github.com/deghosal-2026/agent-eval-forge/issues/15)
- [ ] Create `.gitignore`, `.env.example`
- [ ] Initialize git repo and push blank scaffold
- [ ] Configure ruff for linting → [#16](https://github.com/deghosal-2026/agent-eval-forge/issues/16)
- [ ] Configure mypy with strict mode → [#17](https://github.com/deghosal-2026/agent-eval-forge/issues/17)
- [ ] Configure pytest with basic conftest → [#18](https://github.com/deghosal-2026/agent-eval-forge/issues/18)
- [ ] Set up GitHub Actions CI pipeline (lint, typecheck, test) → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
- [ ] Configure Dependabot for dependency updates → [#20](https://github.com/deghosal-2026/agent-eval-forge/issues/20)
- [ ] Write `README.md` from PRD/spec → [#21](https://github.com/deghosal-2026/agent-eval-forge/issues/21)
- [ ] Write `LICENSE` (MIT) → [#22](https://github.com/deghosal-2026/agent-eval-forge/issues/22)
- [ ] Write `CONTRIBUTING.md` → [#23](https://github.com/deghosal-2026/agent-eval-forge/issues/23)
- [ ] Write `CHANGELOG.md` → [#24](https://github.com/deghosal-2026/agent-eval-forge/issues/24)

### Success Criteria

- `pytest` runs and passes on a basic placeholder test
- `ruff check` passes with zero errors
- `mypy --strict` passes with zero errors
- CI pipeline passes on push
- Package installs locally with `pip install -e .`


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M1: Core Runner

**Goal:** Load scenario packs, invoke agents through adapters, capture normalized run artifacts.

### Checklist

- [ ] Implement `ScenarioPack` model (`src/evalforge/models/pack.py`) → [#71](https://github.com/deghosal-2026/agent-eval-forge/issues/71)
  - [ ] Scenario data model (id, title, goal, input, context, tools, expected, metrics, tags, budget)
  - [ ] Pack metadata model (name, version, description, min_evalforge)
- [ ] YAML parser with schema validation → [#25](https://github.com/deghosal-2026/agent-eval-forge/issues/25)
  - [ ] JSON parser as secondary format
  - [ ] Validation: duplicate IDs, missing required fields, valid metric names, threshold ranges
- [ ] Implement `RunArtifact` model (`src/evalforge/models/artifact.py`) → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [ ] Run metadata (id, scenario_id, timestamps, status)
- [ ] Output model (final text, structured JSON) → [#55](https://github.com/deghosal-2026/agent-eval-forge/issues/55)
  - [ ] Trajectory model (steps, tool calls, tool results, timing)
  - [ ] Cost model (tokens, USD, breakdown)
  - [ ] Error model (type, message, stack trace)
  - [ ] Serialization to JSON
  - [ ] Deserialization from JSON
- [ ] Implement Agent Adapter contract (`src/evalforge/adapters/base.py`) → [#27](https://github.com/deghosal-2026/agent-eval-forge/issues/27)
- [ ] `Adapter` abstract base class → [#27](https://github.com/deghosal-2026/agent-eval-forge/issues/27)
  - [ ] `run(scenario, config) -> RunArtifact` signature
  - [ ] Timeout enforcement per scenario
  - [ ] Error capture and normalization
- [ ] Implement Subprocess Adapter (`src/evalforge/adapters/subprocess.py`) → [#28](https://github.com/deghosal-2026/agent-eval-forge/issues/28)
  - [ ] Invoke agent binary with scenario input
  - [ ] Capture stdout/stderr
  - [ ] Parse output into RunArtifact
  - [ ] Handle timeouts, crashes, non-zero exits
- [ ] Implement Python Import Adapter (`src/evalforge/adapters/python_import.py`) → [#29](https://github.com/deghosal-2026/agent-eval-forge/issues/29)
  - [ ] Import and call Python function by module path
  - [ ] Pass scenario input, tools, context
  - [ ] Capture return value and exceptions
- [ ] Implement HTTP Adapter (`src/evalforge/adapters/http.py`) → [#30](https://github.com/deghosal-2026/agent-eval-forge/issues/30)
  - [ ] POST scenario to agent endpoint
- [ ] Handle connection errors, timeouts, non-200 responses → [#28](https://github.com/deghosal-2026/agent-eval-forge/issues/28)
- [ ] Implement `Runner` class (`src/evalforge/runner.py`) → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [ ] Load scenario pack → [#59](https://github.com/deghosal-2026/agent-eval-forge/issues/59)
  - [ ] Resolve adapter from config
  - [ ] Run single scenario (`runner.run_one(scenario_id)`)
- [ ] Run full pack (`runner.run_all()`) → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
  - [ ] Run filtered by tag (`runner.run_all(tags=["retrieval"])`)
  - [ ] Save artifacts to `.evalforge/runs/`
- [ ] Write unit tests for all models → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write integration tests for all adapter types with mock agents → [#108](https://github.com/deghosal-2026/agent-eval-forge/issues/108)

### Success Criteria

- Can `runner.run_one("scenario-01")` with a mock subprocess agent and get a valid `RunArtifact`
- All adapters exercise their full path (subprocess, python import, HTTP)
- Timeout kills a stuck agent and marks artifact as `timeout`
- Invalid scenario YAML raises clear parse error with line number
- All model tests pass with >90% coverage on models


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M2: Scoring Engine

**Goal:** Score run artifacts against scenario expectations using deterministic and LLM-as-judge scorers.

### Checklist

- [ ] Implement `Scorer` base class (`src/evalforge/scoring/base.py`) → [#34](https://github.com/deghosal-2026/agent-eval-forge/issues/34)
  - [ ] `name` attribute
  - [ ] `score(artifact, scenario) -> ScoreResult` method
- [ ] Implement `ScoreResult` model (`src/evalforge/scoring/result.py`) → [#34](https://github.com/deghosal-2026/agent-eval-forge/issues/34)
  - [ ] metric name, score (0.0-1.0), threshold, passed (bool), detail (dict)
- [ ] Implement deterministic scorers (`src/evalforge/scoring/deterministic/`) → [#49](https://github.com/deghosal-2026/agent-eval-forge/issues/49)
- [ ] `ExactMatchScorer` — output equals expected with case-insensitive option → [#35](https://github.com/deghosal-2026/agent-eval-forge/issues/35)
  - [ ] `SchemaValidScorer` — JSON Schema validation
  - [ ] `FieldPresenceScorer` — required fields present
  - [ ] `ToolCalledScorer` — specific tool invoked
  - [ ] `ToolNotCalledScorer` — specific tool not invoked
- [ ] `ToolArgsMatchScorer` — tool arguments match (exact, subset, superset) → [#39](https://github.com/deghosal-2026/agent-eval-forge/issues/39)
  - [ ] `ToolSequenceScorer` — tools called in expected order
  - [ ] `StepCountScorer` — steps within budget
  - [ ] `TokenCountScorer` — tokens within budget
  - [ ] `CostBudgetScorer` — cost within budget
  - [ ] `TimeoutScorer` — run completed without timeout
- [ ] Implement LLM-as-Judge scorers (`src/evalforge/scoring/judge/`) → [#50](https://github.com/deghosal-2026/agent-eval-forge/issues/50)
- [ ] Judge client abstraction (OpenAI, Anthropic, local) → [#42](https://github.com/deghosal-2026/agent-eval-forge/issues/42)
  - [ ] `TaskCompletionScorer` — did the agent accomplish the goal?
  - [ ] `OutputCorrectnessScorer` — is the answer factually correct?
  - [ ] `SynthesisQualityScorer` — quality of multi-source synthesis
  - [ ] `ClarificationQualityScorer` — quality of clarifying question
  - [ ] `ConflictExplanationScorer` — quality of conflict detection
  - [ ] `HallucinationCheckScorer` — did the agent fabricate facts?
  - [ ] `RefusalQualityScorer` — quality of safe refusal
  - [ ] `PlanQualityScorer` — quality of proposed plan
  - [ ] `RecoveryQualityScorer` — quality of failure recovery
- [ ] Implement `HybridScorer` (`src/evalforge/scoring/hybrid.py`) → [#51](https://github.com/deghosal-2026/agent-eval-forge/issues/51)
  - [ ] Deterministic gate first, judge fallback
  - [ ] Configurable per scenario
- [ ] Implement `ScoringEngine` (`src/evalforge/scoring/engine.py`) → [#47](https://github.com/deghosal-2026/agent-eval-forge/issues/47)
- [ ] Run all deterministic scorers for a scenario → [#49](https://github.com/deghosal-2026/agent-eval-forge/issues/49)
  - [ ] Run LLM judge scorers only when configured and needed
  - [ ] Aggregate scores per scenario
- [ ] Apply evaluation hierarchy: safety > correctness > efficiency → [#47](https://github.com/deghosal-2026/agent-eval-forge/issues/47)
  - [ ] Safety violations produce hard fail
  - [ ] Correctness/efficiency regressions warn by default
- [ ] Implement custom scorer registration (`src/evalforge/scoring/registry.py`) → [#48](https://github.com/deghosal-2026/agent-eval-forge/issues/48)
  - [ ] `@register_scorer` decorator
  - [ ] Entry point discovery
- [ ] Write unit tests for all deterministic scorers → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write integration tests for LLM-as-judge scorers with mock judge → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write tests for hybrid scoring → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write tests for evaluation hierarchy enforcement → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)

### Success Criteria

- All 11 deterministic scorers pass with mock artifacts
- LLM-as-judge scorers produce scores with rationale
- Hybrid scorer falls back to judge when deterministic gate fails
- Safety violation produces `passed=False` with hard-fail flag
- Custom scorer registered via decorator is discoverable
- All scorer tests pass with >90% coverage


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M3: Comparison & Baselines

**Goal:** Save baseline snapshots, compare candidate runs against baselines, produce comparison reports.

### Checklist

- [ ] Implement `Baseline` model (`src/evalforge/baselines/model.py`) → [#89](https://github.com/deghosal-2026/agent-eval-forge/issues/89)
  - [ ] Baseline metadata (name, pack, pack_version, agent info, git_sha, created)
  - [ ] List of run artifacts aggregated into baseline
  - [ ] Serialization to JSON
- [ ] Implement `BaselineStore` (`src/evalforge/baselines/store.py`) → [#89](https://github.com/deghosal-2026/agent-eval-forge/issues/89)
  - [ ] Save baseline from run artifacts (`save(name, runs)`)
  - [ ] Load baseline by name (`load(name)`)
  - [ ] List all baselines (`list()`)
  - [ ] Validate baseline against current pack version
  - [ ] Support git-tag referenced baselines
- [ ] Implement `ComparisonEngine` (`src/evalforge/comparison/engine.py`) → [#54](https://github.com/deghosal-2026/agent-eval-forge/issues/54)
  - [ ] Compare individual runs against baseline
  - [ ] Aggregate comparison at three levels: → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)
    - [ ] Per scenario — was this specific scenario better or worse?
    - [ ] Per family/tag — did a class of scenarios regress?
    - [ ] Aggregate pack level — overall score delta
  - [ ] Detect new failures, new passes, regressions, improvements
  - [ ] Calculate score deltas per metric
- [ ] Implement `ComparisonReport` model (`src/evalforge/comparison/report.py`) → [#58](https://github.com/deghosal-2026/agent-eval-forge/issues/58)
  - [ ] Summary statistics (total, passed, failed, safety violations, regressions)
  - [ ] Per-scenario deltas
  - [ ] Per-family deltas
  - [ ] Aggregate deltas
- [ ] Cost breakdown (agent + judge) → [#45](https://github.com/deghosal-2026/agent-eval-forge/issues/45)
  - [ ] JSON serialization
  - [ ] Markdown report generation
  - [ ] CI-friendly output (exit codes, summary)
- [ ] Write unit tests for baseline save/load/validate → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write integration tests for comparison with known artifacts → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write tests for comparison report generation (JSON + markdown) → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)

### Success Criteria

- Can save a baseline from a set of runs and load it back
- Can compare a candidate run against a baseline and get per-scenario + aggregate deltas
- Safety violation produces exit code 4 in comparison report
- Markdown report is human-readable with pass/fail/improvement breakdown
- Baseline validation warns when pack version differs
- Comparison correctly identifies regressions (score drop) and improvements (score gain)


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M4: Launch Scenarios 1-5

**Goal:** Implement and validate the first half of the launch pack scenarios.

### Checklist

- [ ] Write scenario pack YAML: `scenarios/core-launch.yaml` → [#82](https://github.com/deghosal-2026/agent-eval-forge/issues/82)
- [ ] Implement Scenario 1: Single-Tool Factual Retrieval → [#68](https://github.com/deghosal-2026/agent-eval-forge/issues/68)
  - [ ] `launch-01-account-policy`: Policy lookup with exact match
  - [ ] `launch-01-system-status`: Health check with schema validation
- [ ] Implement Scenario 2: Multi-Tool Retrieval Synthesis → [#68](https://github.com/deghosal-2026/agent-eval-forge/issues/68)
  - [ ] `launch-02-cross-source`: Customer summary from two tools
  - [ ] `launch-02-incident-context`: Incident context assembly
- [ ] Implement Scenario 3: Structured JSON Extraction → [#62](https://github.com/deghosal-2026/agent-eval-forge/issues/62)
  - [ ] `launch-03-incident-extraction`: Structured extraction from text
  - [ ] `launch-03-config-extraction`: Config block extraction from document
- [ ] Implement Scenario 4: Tool Argument Precision → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
  - [ ] `launch-04-deploy-args`: Precise deployment arguments
  - [ ] `launch-04-time-range-args`: Time range argument precision
- [ ] Implement Scenario 5: Tool Avoidance When No Tool Is Needed → [#68](https://github.com/deghosal-2026/agent-eval-forge/issues/68)
  - [ ] `launch-05-no-tool-needed`: Direct answer without tools
  - [ ] `launch-05-simple-calculation`: Simple calculation without tools
- [ ] Create mock agents for each scenario to verify scoring → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Mock agent that passes each scenario → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Mock agent that fails each scenario in expected ways → [#74](https://github.com/deghosal-2026/agent-eval-forge/issues/74)
- [ ] Write tests for each scenario → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
  - [ ] Test that passing agent scores correctly
  - [ ] Test that failing agent is caught
- [ ] Test that each expected failure mode is detectable → [#74](https://github.com/deghosal-2026/agent-eval-forge/issues/74)
- [ ] Write fixture data for deterministic runs → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
  - [ ] `fixtures/policy_lookup.json`
  - [ ] `fixtures/health_check.json`
  - [ ] `fixtures/customer_lookup.json`
  - [ ] `fixtures/ticket_search.json`
  - [ ] `fixtures/monitoring_query.json`
  - [ ] `fixtures/deployment_history.json`
  - [ ] `fixtures/deploy_rollback.json`
  - [ ] `fixtures/log_query.json`

### Success Criteria

- All 10 scenarios load and validate without errors
- Each scenario has a passing mock agent and a failing mock agent
- Each failure mode defined in the scenario is triggered and caught
- Deterministic scorers correctly score all scenarios
- Fixture data covers all tool calls in these scenarios
- `evalforge validate --pack scenarios/core-launch.yaml --strict` passes


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M5: Launch Scenarios 6-10

**Goal:** Implement and validate the second half of the launch pack scenarios.

### Checklist

- [ ] Implement Scenario 6: Disallowed Tool Refusal → [#68](https://github.com/deghosal-2026/agent-eval-forge/issues/68)
  - [ ] `launch-06-prod-delete-refusal`: Refuse destructive tool
  - [ ] `launch-06-staging-vs-prod-refusal`: Staging vs production boundary
- [ ] Implement Scenario 7: Ambiguous User Request Clarification → [#69](https://github.com/deghosal-2026/agent-eval-forge/issues/69)
  - [ ] `launch-07-env-ambiguity`: Environment ambiguity
  - [ ] `launch-07-scope-ambiguity`: Scope ambiguity
- [ ] Implement Scenario 8: Budget-Constrained Completion → [#70](https://github.com/deghosal-2026/agent-eval-forge/issues/70)
  - [ ] `launch-08-step-budget`: Step budget enforcement
  - [ ] `launch-08-tight-cost-budget`: Tight cost budget
- [ ] Implement Scenario 9: Graceful Timeout / Recovery → [#71](https://github.com/deghosal-2026/agent-eval-forge/issues/71)
  - [ ] `launch-09-tool-timeout`: Tool timeout recovery
  - [ ] `launch-09-partial-data-failure`: Partial data failure recovery
- [ ] Implement Scenario 10: Coding-Agent Regression → [#72](https://github.com/deghosal-2026/agent-eval-forge/issues/72)
  - [ ] `launch-10-diff-review`: Code diff risk assessment
  - [ ] `launch-10-test-classify`: Test failure classification
- [ ] Create mock agents for each scenario → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Mock agent that passes each scenario → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Mock agent that fails in the specific failure mode → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Write tests for each scenario → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write fixture data for deterministic runs → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
  - [ ] `fixtures/customer_delete.json`
  - [ ] `fixtures/deploy_production.json`
  - [ ] `fixtures/deploy_staging.json`
  - [ ] `fixtures/service_restart.json`
- [ ] `fixtures/data_purge.json` → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
  - [ ] `fixtures/incident_create.json`
  - [ ] `fixtures/job_status.json`
  - [ ] `fixtures/metrics_query.json`
- [ ] End-to-end test: run full launch pack against mock agents → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
- [ ] Verify all 20 scenarios run to completion → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)
- [ ] Verify passing mock agents produce green report → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Verify failing mock agents produce red report with specific failures → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Verify safety violations produce exit code 4 → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)

### Success Criteria

- All 20 launch scenarios load, validate, run, and score correctly
- Safety scenarios (disallowed tools, approval boundaries) catch violations
- Budget scenarios enforce step/token/cost limits
- Recovery scenarios detect retry loops and partial failures
- Coding scenarios produce meaningful review and classification results
- Full pack run produces a correct JSON + markdown report


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M6: Framework Adapters

**Goal:** Ship tested, documented adapters for LangGraph and PydanticAI.

### Checklist

- [ ] Implement LangGraph Adapter (`src/evalforge/adapters/langgraph.py`) → [#81](https://github.com/deghosal-2026/agent-eval-forge/issues/81)
  - [ ] Invoke LangGraph graph with scenario input
  - [ ] Extract state graph trajectory nodes
  - [ ] Normalize tool calls into EvalForge tool_call format
  - [ ] Capture final output from graph
  - [ ] Handle interrupts / human-in-the-loop states
- [ ] Handle graph errors and timeouts → [#28](https://github.com/deghosal-2026/agent-eval-forge/issues/28)
- [ ] Implement PydanticAI Adapter (`src/evalforge/adapters/pydantic_ai.py`) → [#82](https://github.com/deghosal-2026/agent-eval-forge/issues/82)
  - [ ] Invoke PydanticAI agent with scenario input
  - [ ] Extract typed output from agent result
  - [ ] Capture tool usage from agent run context
  - [ ] Map structured output to EvalForge schema expectations
  - [ ] Handle agent errors and validation failures
- [ ] Write example agents for each framework → [#108](https://github.com/deghosal-2026/agent-eval-forge/issues/108)
- [ ] `examples/langgraph_agent.py` — simple tool-using agent → [#114](https://github.com/deghosal-2026/agent-eval-forge/issues/114)
- [ ] `examples/pydantic_ai_agent.py` — simple tool-using agent → [#80](https://github.com/deghosal-2026/agent-eval-forge/issues/80)
- [ ] Write integration tests → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] LangGraph adapter: run launch scenarios 1-5 against example agent → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
- [ ] PydanticAI adapter: run launch scenarios 1-5 against example agent → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
- [ ] Verify trajectory capture matches agent's actual execution path → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)
- [ ] Write adapter documentation
  - [ ] `docs/adapters/langgraph.md`
  - [ ] `docs/adapters/pydantic-ai.md`
  - [ ] Adapter contract specification
  - [ ] How to write a custom adapter

### Success Criteria

- LangGraph adapter correctly invokes, captures trajectory, normalizes tool calls
- PydanticAI adapter correctly captures typed output and tool usage
- At least 5 launch scenarios run end-to-end with each adapter
- Trajectory in artifact matches agent's actual execution
- Both example agents are runnable with `python examples/langgraph_agent.py` etc.
- Adapter docs are complete and followable


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M7: CLI & pytest

**Goal:** Complete CLI surface, pytest plugin, and all output formats.

### Checklist

- [ ] Implement CLI commands (`src/evalforge/cli/`) → [#94](https://github.com/deghosal-2026/agent-eval-forge/issues/94)
  - [ ] `evalforge run` — run a scenario pack → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
    - [ ] `--pack` (required)
    - [ ] `--agent` (required)
    - [ ] `--baseline` (optional)
    - [ ] `--judge` (optional)
    - [ ] `--output` (default: `.evalforge/`)
- [ ] `--output-format` (json, markdown, default: both) → [#93](https://github.com/deghosal-2026/agent-eval-forge/issues/93)
    - [ ] `--workers` (default: 1)
    - [ ] `--timeout` (default: 120)
    - [ ] `--fixtures` / `--live` (default: fixtures)
    - [ ] `--ci` flag for CI mode
    - [ ] `--tags` filter
  - [ ] `evalforge validate` — validate packs, agents, baselines → [#87](https://github.com/deghosal-2026/agent-eval-forge/issues/87)
    - [ ] `--pack`
    - [ ] `--agent`
    - [ ] `--baseline`
    - [ ] `--strict`
    - [ ] `--check-fixtures`
  - [ ] `evalforge compare` — compare two runs → [#88](https://github.com/deghosal-2026/agent-eval-forge/issues/88)
    - [ ] `--candidate`
    - [ ] `--baseline`
  - [ ] `evalforge baseline` — baseline management
    - [ ] `baseline save --name <name> --run <run>`
    - [ ] `baseline list`
    - [ ] `baseline validate --baseline <name> --pack <pack>`
- [ ] `evalforge cache clear` → [#90](https://github.com/deghosal-2026/agent-eval-forge/issues/90)
- [ ] `evalforge plugins list` → [#90](https://github.com/deghosal-2026/agent-eval-forge/issues/90)
- [ ] `evalforge --help` with useful docs → [#91](https://github.com/deghosal-2026/agent-eval-forge/issues/91)
- [ ] Implement pytest plugin (`src/evalforge/pytest_plugin.py`) → [#92](https://github.com/deghosal-2026/agent-eval-forge/issues/92)
- [ ] `evalforge test run` command → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [ ] Auto-discovery of scenario packs
- [ ] pytest fixture for scenario injection → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
  - [ ] pytest markers for tags (`@pytest.mark.evalforge.tags("retrieval")`)
- [ ] Custom pytest report with scenario pass/fail → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [ ] Implement output formatting → [#93](https://github.com/deghosal-2026/agent-eval-forge/issues/93)
  - [ ] JSON output (default, CI-friendly)
  - [ ] Markdown report (human-readable)
  - [ ] Terminal output (colored, progress during run)
  - [ ] GitHub Actions summary comment → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
- [ ] Write CLI integration tests → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] `evalforge run` with minimal config → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [ ] `evalforge validate` on valid and invalid packs
  - [ ] `evalforge compare` between two known runs
- [ ] `evalforge baseline save/list/validate` → [#89](https://github.com/deghosal-2026/agent-eval-forge/issues/89)
  - [ ] Exit codes verified for all scenarios
- [ ] Write pytest plugin integration tests → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)

### Success Criteria

- `evalforge run --pack scenarios/core-launch.yaml --agent python:my_agent.py` completes successfully
- `evalforge validate --pack scenarios/core-launch.yaml --strict` passes
- `evalforge compare` produces correct delta report
- `evalforge baseline save/list/validate` works end-to-end
- Pytest plugin runs scenarios as pytest tests with correct pass/fail
- All CLI exit codes (0-4) are correctly produced
- JSON and markdown reports are well-formed


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M8: CI & Polish

**Goal:** CI integration, caching, parallel execution, fixtures, validation, and security hardening.

### Checklist

- [ ] Implement CI integration → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
  - [ ] `--ci` flag: JSON-only output, no prompts, structured exit
  - [ ] GitHub Actions workflow template
- [ ] GitLab CI template → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
  - [ ] CI summary comment generation
  - [ ] Artifact upload for `.evalforge/` directory
- [ ] Implement caching system
- [ ] Judge result cache (hash-based, 24h TTL) → [#97](https://github.com/deghosal-2026/agent-eval-forge/issues/97)
- [ ] Run result cache (session-scoped) → [#98](https://github.com/deghosal-2026/agent-eval-forge/issues/98)
  - [ ] Schema validation cache (pack lifetime)
  - [ ] Cost-saved reporting in run output
- [ ] `evalforge cache clear` command → [#90](https://github.com/deghosal-2026/agent-eval-forge/issues/90)
  - [ ] `--no-cache` flag
- [ ] Implement parallel execution → [#99](https://github.com/deghosal-2026/agent-eval-forge/issues/99)
  - [ ] `--workers N` flag
  - [ ] Per-worker subprocess isolation
  - [ ] Worker timeout enforcement
  - [ ] Resource limits (`--max-memory`, `--max-cpu`)
  - [ ] Thread-safe result aggregation
- [ ] Implement fixture system → [#100](https://github.com/deghosal-2026/agent-eval-forge/issues/100)
  - [ ] `--fixtures` mode (default, deterministic)
  - [ ] `--live` mode (real tool calls)
  - [ ] `ToolStub` class for intercepting tool calls
  - [ ] Simulated latency (`delay_ms`)
- [ ] Fixture validation (`evalforge validate --check-fixtures`) → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
- [ ] Implement validation mode → [#101](https://github.com/deghosal-2026/agent-eval-forge/issues/101)
  - [ ] Pack validation (duplicate IDs, required fields, valid metrics)
  - [ ] Agent validation (import check, connectivity)
  - [ ] Baseline validation (file exists, version compatibility)
  - [ ] `--strict` mode (warnings → errors)
  - [ ] Pre-flight CI validation
- [ ] Implement security model → [#102](https://github.com/deghosal-2026/agent-eval-forge/issues/102)
  - [ ] API key sanitization in all logs and artifacts
  - [ ] Subprocess sandbox (no shell, no API key passthrough)
  - [ ] `--sandbox` flag for untrusted packs
  - [ ] Audit trail for every run
  - [ ] Scenario trust boundaries (built-in/local/external)
- [ ] Write integration tests for all polish features → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [ ] Write security review doc

### Success Criteria

- CI pipeline runs EvalForge and reports results as GitHub check
- Cache avoids redundant LLM judge calls and reports cost saved
- Parallel execution with 4 workers completes faster than serial without errors
- Fixtures mode produces deterministic results (identical runs = identical scores)
- `evalforge validate --strict` catches all known error cases
- API keys are never present in logs, artifacts, or agent environment


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M9: OSS Readiness

**Goal:** OpenSSF Best Practices badge, polished docs, community files, and contributor experience.

### Checklist

- [ ] OpenSSF Best Practices badge → [#104](https://github.com/deghosal-2026/agent-eval-forge/issues/104)
  - [ ] Passing level criteria met
  - [ ] Badge embed in README
  - [ ] Frontmatter update in vault project note
- [ ] Documentation
- [ ] `README.md` — project description, quickstart, comparison table → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)
  - [ ] `docs/PRD.md` — approved (✓)
  - [ ] `docs/spec.md` — approved (✓)
  - [ ] `docs/adapters/langgraph.md` — LangGraph adapter usage
  - [ ] `docs/adapters/pydantic-ai.md` — PydanticAI adapter usage
  - [ ] `docs/adapters/custom.md` — how to write a custom adapter
- [ ] `docs/scoring.md` — scoring API and custom scorer guide → [#105](https://github.com/deghosal-2026/agent-eval-forge/issues/105)
- [ ] `docs/scenarios.md` — scenario pack authoring guide → [#106](https://github.com/deghosal-2026/agent-eval-forge/issues/106)
- [ ] `docs/ci.md` — CI integration guide → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
- [ ] `docs/examples/` — example scenarios and agents → [#108](https://github.com/deghosal-2026/agent-eval-forge/issues/108)
- [ ] Community files
  - [ ] `LICENSE` (✓)
  - [ ] `CONTRIBUTING.md`
  - [ ] `CODE_OF_CONDUCT.md`
  - [ ] `SECURITY.md`
  - [ ] `SUPPORT.md`
  - [ ] `GOVERNANCE.md`
- [ ] Issue templates (bug, feature, scenario-pack) → [#112](https://github.com/deghosal-2026/agent-eval-forge/issues/112)
  - [ ] PR template
- [ ] Package metadata → [#113](https://github.com/deghosal-2026/agent-eval-forge/issues/113)
- [ ] Package description, keywords, classifiers in `pyproject.toml` → [#113](https://github.com/deghosal-2026/agent-eval-forge/issues/113)
  - [ ] Verified PyPI name availability
  - [ ] Version set to `0.1.0`
- [ ] Clean repo
- [ ] Squash history to clean initial commit → [#121](https://github.com/deghosal-2026/agent-eval-forge/issues/121)
- [ ] No secrets, API keys, or credentials in repo → [#122](https://github.com/deghosal-2026/agent-eval-forge/issues/122)
  - [ ] No generated files tracked (except `.evalforge/` if needed for examples)
- [ ] Write launch article draft → [#126](https://github.com/deghosal-2026/agent-eval-forge/issues/126)

### Success Criteria

- OpenSSF Best Practices badge at Passing level displayed in README
- All docs files exist and are complete
- All community files exist
- Repo is clean and ready for public visibility
- Launch article draft is ready for review


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M10: Ship v0.1

**Goal:** Final integration, GitHub release, PyPI publish.

### Checklist

- [ ] Final integration test
- [ ] Run full launch pack against LangGraph example agent → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
- [ ] Run full launch pack against PydanticAI example agent → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
- [ ] Run full launch pack against mock agents (all passing) → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
  - [ ] Verify all reports are correct
  - [ ] Verify all exit codes
  - [ ] Verify CI pipeline passes
- [ ] Publish to PyPI → [#119](https://github.com/deghosal-2026/agent-eval-forge/issues/119)
  - [ ] Build package: `python -m build` → [#117](https://github.com/deghosal-2026/agent-eval-forge/issues/117)
- [ ] Verify package contents: `twine check dist/*` → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)
- [ ] Test install from built package: `pip install dist/*.whl` → [#118](https://github.com/deghosal-2026/agent-eval-forge/issues/118)
- [ ] Publish to PyPI: `twine upload dist/*` → [#119](https://github.com/deghosal-2026/agent-eval-forge/issues/119)
- [ ] Create GitHub release → [#120](https://github.com/deghosal-2026/agent-eval-forge/issues/120)
  - [ ] Tag `v0.1.0`
  - [ ] Release notes with changelog
  - [ ] Attach built artifacts
  - [ ] Link to documentation

### Success Criteria

- `pip install agent-eval-forge` works from PyPI
- GitHub release is visible with release notes
- Full test suite passes on clean install
- OpenSSF badge remains at Passing after release


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M11: OSS Cleanup & Launch

**Goal:** Repo cleanup, history squash, public visibility, launch article, community engagement.

### Checklist

- [ ] Repo cleanup
- [ ] Squash git history to clean initial commit → [#121](https://github.com/deghosal-2026/agent-eval-forge/issues/121)
- [ ] Scan repo for secrets, API keys, credentials (trufflehog, git-secrets) → [#122](https://github.com/deghosal-2026/agent-eval-forge/issues/122)
  - [ ] Verify no generated files tracked (`.evalforge/` but not build artifacts)
- [ ] Verify all docs links work and cross-reference each other → [#123](https://github.com/deghosal-2026/agent-eval-forge/issues/123)
- [ ] Verify README quickstart works on a clean clone → [#124](https://github.com/deghosal-2026/agent-eval-forge/issues/124)
- [ ] Make repo public → [#125](https://github.com/deghosal-2026/agent-eval-forge/issues/125)
- [ ] Launch article → [#127](https://github.com/deghosal-2026/agent-eval-forge/issues/127)
- [ ] Final review and edit → [#126](https://github.com/deghosal-2026/agent-eval-forge/issues/126)
- [ ] Publish to dev.to → [#126](https://github.com/deghosal-2026/agent-eval-forge/issues/126)
- [ ] Cross-post to Hashnode → [#127](https://github.com/deghosal-2026/agent-eval-forge/issues/127)
- [ ] Share on relevant communities (Reddit, Discord, HN, LinkedIn) → [#128](https://github.com/deghosal-2026/agent-eval-forge/issues/128)
- [ ] Post-launch
- [ ] Respond to community comments within 24h → [#129](https://github.com/deghosal-2026/agent-eval-forge/issues/129)
- [ ] Triage incoming issues → [#130](https://github.com/deghosal-2026/agent-eval-forge/issues/130)
- [ ] Draft v0.2 roadmap from early feedback → [#130](https://github.com/deghosal-2026/agent-eval-forge/issues/130)

### Success Criteria

- Repo is public with clean git history
- No secrets or credentials in any commit
- README quickstart works on a fresh clone
- Launch article is live with community engagement
- First community issues are triaged within 24h


### Milestone Exit Gates
- [ ] Code review completed
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)
- [ ] Security scan clean (trufflehog, bandit) → [#122](https://github.com/deghosal-2026/agent-eval-forge/issues/122)

---

## Article Series

| Article | Topic | Milestone Gate |
|---------|-------|----------------|
| 1/5 | "Why Agent Evaluation is Harder Than Model Evaluation" | After M3 (scoring engine works) |
| 2/5 | "Scenario Packs and Regression Testing for Agent Behavior" | After M5 (all launch scenarios work) |
| 3/5 | "Trajectory Scoring: Why the Agent's Path Matters" | After M5 |
| 4/5 | "Safety-First Agent Gating: Catch Boundary Violations Before They Ship" | After M6 (adapters + safety scenarios) |
| 5/5 | "EvalForge: A Framework-Agnostic Release Gate for AI Agents" | After M10 (launch) |

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM judge costs exceed budget during scenario development | Medium | Use mock judges during dev, real judges only in CI/integration |
| LangGraph/PydanticAI API changes break adapters | Medium | Pin framework versions, test against latest on schedule |
| Scenario packs are too brittle (depend on exact tool output) | Low | Fixtures system decouples scenarios from live tool behavior |
| v0.1 scope too broad for timeline | Medium | M4-M5 scenarios are the riskiest; can reduce to 6 launch groups if needed |
| PyPI name unavailable | Low | Verify early; fallback `agent-eval-forge` confirmed available |