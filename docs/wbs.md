# Agent Eval Forge — Work Breakdown Structure

**Status:** Approved  
**Date:** 2026-07-28  
**Dependencies:** PRD v1.0 (approved), Spec v1.0 (approved)

## Milestone Overview

| Milestone | Scope | Target |
|-----------|-------|--------|
| M0: Scaffold | Repo, config, CI, package structure | Week 2 (Jul 28 - Aug 3) |
| M1: Core Runner | Scenario loading, agent invocation, artifact capture | Week 3 (Aug 4-10) |
| M2: Scoring Engine | Deterministic scorers, LLM-as-judge, hybrid scoring | **Complete** (Aug 4-10) |
| M3: Comparison & Baselines | Baseline save/load, comparison engine, reporting | **Complete** (Aug 4-10) |
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

- [x] Initialize Python package structure (`agent-eval-forge/` with `src/evalforge/`) → [#13](https://github.com/deghosal-2026/agent-eval-forge/issues/13)
- [x] Configure `pyproject.toml` with dependencies and entry points → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96) (basic config; full CI integration is M8)
- [x] Set up `uv` or `pip` for dependency management → [#15](https://github.com/deghosal-2026/agent-eval-forge/issues/15)
- [x] Create `.gitignore`, `.env.example`
- [x] Initialize git repo and push blank scaffold
- [x] Configure ruff for linting → [#16](https://github.com/deghosal-2026/agent-eval-forge/issues/16)
- [x] Configure mypy with strict mode → [#17](https://github.com/deghosal-2026/agent-eval-forge/issues/17)
- [x] Configure pytest with basic conftest → [#18](https://github.com/deghosal-2026/agent-eval-forge/issues/18)
- [x] Set up GitHub Actions CI pipeline (lint, typecheck, test) → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96) (basic pipeline; full CI integration is M8)
- [x] Configure Dependabot for dependency updates → [#20](https://github.com/deghosal-2026/agent-eval-forge/issues/20)
- [x] Write `README.md` from PRD/spec → [#21](https://github.com/deghosal-2026/agent-eval-forge/issues/21)
- [x] Write `LICENSE` (MIT) → [#22](https://github.com/deghosal-2026/agent-eval-forge/issues/22)
- [x] Write `CONTRIBUTING.md` → [#23](https://github.com/deghosal-2026/agent-eval-forge/issues/23)
- [x] Write `CHANGELOG.md` → [#24](https://github.com/deghosal-2026/agent-eval-forge/issues/24)

### Success Criteria

- `pytest` runs and passes on a basic placeholder test
- `ruff check` passes with zero errors
- `mypy --strict` passes with zero errors
- CI pipeline passes on push
- Package installs locally with `pip install -e .`


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M1: Core Runner

**Goal:** Load scenario packs, invoke agents through adapters, capture normalized run artifacts.

### Checklist

- [x] Implement `ScenarioPack` model (`src/evalforge/models/pack.py`) → [#71](https://github.com/deghosal-2026/agent-eval-forge/issues/71)
  - [x] Scenario data model (id, title, goal, input, context, tools, expected, metrics, tags, budget)
  - [x] Pack metadata model (name, version, description, min_evalforge)
- [x] YAML parser with schema validation → [#25](https://github.com/deghosal-2026/agent-eval-forge/issues/25)
  - [x] JSON parser as secondary format
  - [x] Validation: duplicate IDs, missing required fields, valid metric names, threshold ranges
- [x] Implement `RunArtifact` model (`src/evalforge/models/artifact.py`) → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [x] Run metadata (id, scenario_id, timestamps, status)
- [x] Output model (final text, structured JSON) → [#55](https://github.com/deghosal-2026/agent-eval-forge/issues/55)
  - [x] Trajectory model (steps, tool calls, tool results, timing)
  - [x] Cost model (tokens, USD, breakdown)
  - [x] Error model (type, message, stack trace)
  - [x] Serialization to JSON
  - [x] Deserialization from JSON
- [x] Implement Agent Adapter contract (`src/evalforge/adapters/base.py`) → [#27](https://github.com/deghosal-2026/agent-eval-forge/issues/27)
- [x] `Adapter` abstract base class → [#27](https://github.com/deghosal-2026/agent-eval-forge/issues/27)
  - [x] `run(scenario, config) -> RunArtifact` signature
  - [x] Timeout enforcement per scenario
  - [x] Error capture and normalization
- [x] Implement Subprocess Adapter (`src/evalforge/adapters/subprocess.py`) → [#28](https://github.com/deghosal-2026/agent-eval-forge/issues/28)
  - [x] Invoke agent binary with scenario input
  - [x] Capture stdout/stderr
  - [x] Parse output into RunArtifact
  - [x] Handle timeouts, crashes, non-zero exits
- [x] Implement Python Import Adapter (`src/evalforge/adapters/python_import.py`) → [#29](https://github.com/deghosal-2026/agent-eval-forge/issues/29)
  - [x] Import and call Python function by module path
  - [x] Pass scenario input, tools, context
  - [x] Capture return value and exceptions
- [x] Implement HTTP Adapter (`src/evalforge/adapters/http.py`) → [#30](https://github.com/deghosal-2026/agent-eval-forge/issues/30)
  - [x] POST scenario to agent endpoint
- [x] Handle connection errors, timeouts, non-200 responses → [#28](https://github.com/deghosal-2026/agent-eval-forge/issues/28)
- [x] Implement `Runner` class (`src/evalforge/runner.py`) → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [x] Load scenario pack → [#59](https://github.com/deghosal-2026/agent-eval-forge/issues/59)
  - [x] Resolve adapter from config
  - [x] Run single scenario (`runner.run_one(scenario_id)`)
- [x] Run full pack (`runner.run_all()`) → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
  - [x] Run filtered by tag (`runner.run_all(tags=["retrieval"])`)
  - [x] Save artifacts to `.evalforge/runs/`
- [x] Author `scenarios/core-launch.yaml` with all 20 launch scenarios (pulled forward from M4/M5) → [#59](https://github.com/deghosal-2026/agent-eval-forge/issues/59)
  - [x] Scenarios 1-5: retrieval, synthesis, extraction, tool args, tool avoidance → [#60](https://github.com/deghosal-2026/agent-eval-forge/issues/60), [#61](https://github.com/deghosal-2026/agent-eval-forge/issues/61), [#62](https://github.com/deghosal-2026/agent-eval-forge/issues/62), [#63](https://github.com/deghosal-2026/agent-eval-forge/issues/63), [#64](https://github.com/deghosal-2026/agent-eval-forge/issues/64)
  - [x] Scenarios 6-10: refusal, ambiguity, budget, recovery, coding → [#68](https://github.com/deghosal-2026/agent-eval-forge/issues/68), [#69](https://github.com/deghosal-2026/agent-eval-forge/issues/69), [#70](https://github.com/deghosal-2026/agent-eval-forge/issues/70), [#71](https://github.com/deghosal-2026/agent-eval-forge/issues/71), [#72](https://github.com/deghosal-2026/agent-eval-forge/issues/72)
- [x] Write unit tests for all models → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [x] Write integration tests for all adapter types with mock agents → [#108](https://github.com/deghosal-2026/agent-eval-forge/issues/108)

### Success Criteria

- Can `runner.run_one("scenario-01")` with a mock subprocess agent and get a valid `RunArtifact`
- All adapters exercise their full path (subprocess, python import, HTTP)
- Timeout kills a stuck agent and marks artifact as `timeout`
- Invalid scenario YAML raises clear parse error with line number
- All model tests pass with >90% coverage on models


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M2: Scoring Engine

**Goal:** Score run artifacts against scenario expectations using deterministic and LLM-as-judge scorers.

### Checklist

- [x] Implement `Scorer` base class (`src/evalforge/scoring/base.py`) → [#34](https://github.com/deghosal-2026/agent-eval-forge/issues/34)
  - [x] `name` attribute
  - [x] `score(artifact, scenario) -> ScoreResult` method
- [x] Implement `ScoreResult` model (`src/evalforge/scoring/result.py`) → [#34](https://github.com/deghosal-2026/agent-eval-forge/issues/34)
  - [x] metric name, score (0.0-1.0), threshold, passed (bool), detail (dict)
- [x] Implement deterministic scorers (`src/evalforge/scoring/deterministic/`) → [#49](https://github.com/deghosal-2026/agent-eval-forge/issues/49)
- [x] `ToolCorrectnessScorer` — called tools are allowed (naming differs from WBS; spec catalog names become registry aliases) → [#35](https://github.com/deghosal-2026/agent-eval-forge/issues/35)
  - [x] `SchemaValidityScorer` — JSON Schema validation
  - [x] `FieldCorrectnessScorer` — required fields present
  - [x] `ZeroDisallowedActionsScorer` — disallowed tool never invoked
  - [x] `UnsafeActionAvoidanceScorer` — safety-class tool avoidance
- [x] `ArgumentCorrectnessScorer` — tool arguments match (exact, subset) → [#39](https://github.com/deghosal-2026/agent-eval-forge/issues/39)
  - [x] `RetryDisciplineGate` — repeated-tool discipline check
  - [x] `StepEfficiencyScorer` — steps within budget
  - [x] `CostBudgetAdherenceScorer` — cost within budget
- [x] Implement LLM-as-Judge scorers (`src/evalforge/scoring/judge/`) → [#50](https://github.com/deghosal-2026/agent-eval-forge/issues/50)
- [x] Judge client abstraction (OpenAI, Anthropic, Ollama, mock) → [#42](https://github.com/deghosal-2026/agent-eval-forge/issues/42)
  - [x] `TaskCompletionScorer` — did the agent accomplish the goal?
  - [x] `OutputCorrectnessScorer` — is the answer factually correct?
  - [x] `SynthesisQualityScorer` — quality of multi-source synthesis
  - [x] `ClarificationQualityScorer` — quality of clarifying question
  - [x] `RefusalQualityScorer` — quality of safe refusal
  - [x] `RecoveryQualityScorer` — quality of failure recovery
  - [x] `BlastRadiusAccuracyScorer`, `VerificationQualityScorer`, `HypothesisQualityScorer`, `EvidenceGroundingScorer`, `HallucinationRateScorer` — remaining judge metrics
- [x] Implement `HybridScorer` (`src/evalforge/scoring/hybrid.py`) → [#51](https://github.com/deghosal-2026/agent-eval-forge/issues/51)
  - [x] Deterministic gate first, judge fallback
  - [x] Configurable per metric via `metric_config`
- [x] Implement `ScoringEngine` (`src/evalforge/scoring/engine.py`) → [#47](https://github.com/deghosal-2026/agent-eval-forge/issues/47)
- [x] Run all deterministic scorers for a scenario → [#49](https://github.com/deghosal-2026/agent-eval-forge/issues/49)
  - [x] Run LLM judge scorers only when configured and needed
  - [x] Aggregate scores per scenario
- [x] Apply evaluation hierarchy: safety > correctness > efficiency → [#47](https://github.com/deghosal-2026/agent-eval-forge/issues/47)
  - [x] Safety violations produce hard fail
  - [x] Correctness/efficiency regressions warn by default
- [x] Implement custom scorer registration (`src/evalforge/scoring/registry.py`) → [#48](https://github.com/deghosal-2026/agent-eval-forge/issues/48)
  - [x] `@register_scorer` decorator
  - [x] Entry point discovery
- [x] Write unit tests for all deterministic scorers → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [x] Write integration tests for LLM-as-judge scorers with mock judge → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [x] Write tests for hybrid scoring → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [x] Write tests for evaluation hierarchy enforcement → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)

### Success Criteria

- All 11 deterministic scorers pass with mock artifacts
- LLM-as-judge scorers produce scores with rationale
- Hybrid scorer falls back to judge when deterministic gate fails
- Safety violation produces `passed=False` with hard-fail flag
- Custom scorer registered via decorator is discoverable
- All scorer tests pass with >90% coverage


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M3: Comparison & Baselines

**Goal:** Save baseline snapshots, compare candidate runs against baselines, produce comparison reports.

### Checklist

- [x] Implement `Baseline` model (`src/evalforge/baselines/model.py`) → [#52](https://github.com/deghosal-2026/agent-eval-forge/issues/52)
  - [x] Baseline metadata (name, pack, pack_version, agent info, git_sha, created)
  - [x] List of run artifacts aggregated into baseline
  - [x] Serialization to JSON
- [x] Implement `BaselineStore` (`src/evalforge/baselines/store.py`) → [#53](https://github.com/deghosal-2026/agent-eval-forge/issues/53)
  - [x] Save baseline from run artifacts (`save(name, runs)`)
  - [x] Load baseline by name (`load(name)`)
  - [x] List all baselines (`list()`)
  - [x] Validate baseline against current pack version
- [x] Implement `ComparisonEngine` (`src/evalforge/comparison/engine.py`) → [#54](https://github.com/deghosal-2026/agent-eval-forge/issues/54)
  - [x] Compare individual runs against baseline
  - [x] Aggregate comparison at three levels:
    - [x] Per scenario — was this specific scenario better or worse?
    - [x] Per family/tag — did a class of scenarios regress?
    - [x] Aggregate pack level — overall score delta
  - [x] Detect new failures, new passes, regressions, improvements
  - [x] Calculate score deltas per metric
- [x] Implement `ComparisonReport` model (`src/evalforge/comparison/report.py`) → [#55](https://github.com/deghosal-2026/agent-eval-forge/issues/55)
  - [x] Summary statistics (total, passed, failed, safety violations, regressions)
  - [x] Per-scenario deltas
  - [x] Per-family deltas
  - [x] Aggregate deltas
- [x] Cost breakdown (agent + judge) → [#55](https://github.com/deghosal-2026/agent-eval-forge/issues/55)
  - [x] JSON serialization
  - [x] Markdown report generation
  - [x] CI-friendly output (exit codes, summary)
- [x] Write unit tests for baseline save/load/validate → [#56](https://github.com/deghosal-2026/agent-eval-forge/issues/56)
- [x] Write integration tests for comparison with known artifacts → [#57](https://github.com/deghosal-2026/agent-eval-forge/issues/57)
- [x] Write tests for comparison report generation (JSON + markdown) → [#58](https://github.com/deghosal-2026/agent-eval-forge/issues/58)

### Success Criteria

- Can save a baseline from a set of runs and load it back
- Can compare a candidate run against a baseline and get per-scenario + aggregate deltas
- Safety violation produces exit code 4 in comparison report
- Markdown report is human-readable with pass/fail/improvement breakdown
- Baseline validation warns when pack version differs
- Comparison correctly identifies regressions (score drop) and improvements (score gain)


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M4: Launch Scenarios 1-5

**Goal:** Validate the first half of the launch pack scenarios with mock agents and fixtures.

> Scenario definitions (`scenarios/core-launch.yaml`, scenarios 1-5) were authored in M1 (pulled forward). M4 focuses on mock agents, tests, and fixture data.

### Checklist

- [x] Create mock agents for each scenario to verify scoring → [#65](https://github.com/deghosal-2026/agent-eval-forge/issues/65)
- [x] Mock agent that passes each scenario → [#65](https://github.com/deghosal-2026/agent-eval-forge/issues/65)
- [x] Mock agent that fails each scenario in expected ways → [#65](https://github.com/deghosal-2026/agent-eval-forge/issues/65)
- [x] Write tests for each scenario → [#66](https://github.com/deghosal-2026/agent-eval-forge/issues/66)
  - [x] Test that passing agent scores correctly
  - [x] Test that failing agent is caught
- [x] Test that each expected failure mode is detectable → [#66](https://github.com/deghosal-2026/agent-eval-forge/issues/66)
- [x] Write fixture data for deterministic runs → [#67](https://github.com/deghosal-2026/agent-eval-forge/issues/67)
  - [x] `fixtures/policy_lookup.json`
  - [x] `fixtures/health_check.json`
  - [x] `fixtures/customer_lookup.json`
  - [x] `fixtures/ticket_search.json`
  - [x] `fixtures/monitoring_query.json`
  - [x] `fixtures/deployment_history.json`
  - [x] `fixtures/deploy_rollback.json`
  - [x] `fixtures/log_query.json`
  - [x] `fixtures/data_export.json`
  - [x] `fixtures/deploy_staging.json`

### Success Criteria

- All 10 scenarios load and validate without errors
- Each scenario has a passing mock agent and a failing mock agent
- Each failure mode defined in the scenario is triggered and caught
- Deterministic scorers correctly score all scenarios
- Fixture data covers all tool calls in these scenarios
- `evalforge validate --pack scenarios/core-launch.yaml --strict` passes


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M5: Launch Scenarios 6-10

**Goal:** Validate the second half of the launch pack scenarios with mock agents and fixtures.

> Scenario definitions (`scenarios/core-launch.yaml`, scenarios 6-10) were authored in M1 (pulled forward). M5 focuses on mock agents, tests, fixture data, and end-to-end pack validation.

### Checklist

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