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
| M7: CLI & pytest | CLI surface, pytest plugin, output formats | Complete |
| M8: CI & Polish | CI integration, fixtures, caching, parallel execution, security | Complete — 2 regression items tracked in M9 |
| M9: Hardening & Security | Hardening, security enforcement, code review findings (Critical→Advanced) | Active — 26/52 review items done in code |
| M9.5: Integration & Field Tests | 15 integration/E2E test gaps, Docker tests, 25-30 field tests, CLI real-process tests | Active — omlx integration done; 14 gaps remain |
| M10: OSS Readiness | OpenSSF badge, docs, LICENSE, README, community files | Week 4 (Aug 11-17) |
| M11: Ship v0.1 | Final integration tests, GitHub release, PyPI | Week 4 (Aug 11-17) |
| M12: OSS Cleanup & Launch | Squash history, public visibility, launch article, community | Week 4 (Aug 11-17) |

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

**Goal:** Validate the second half of the launch pack scenarios with mock agents and fixtures. **Complete** — closes [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73), [#74](https://github.com/deghosal-2026/agent-eval-forge/issues/74), [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75), [#76](https://github.com/deghosal-2026/agent-eval-forge/issues/76).

> Scenario definitions (`scenarios/core-launch.yaml`, scenarios 6-10) were authored in M1 (pulled forward). M5 focuses on mock agents, tests, fixture data, and end-to-end pack validation. Note: the original WBS cited #103/#116/#124; M5 scope maps to #73/#74/#75/#76. `deploy_staging.json` was already added in M4; `deploy_production.json` is a *disallowed* tool (fixture exists but no scenario calls it legitimately).

### Checklist

- [x] Create mock agents for each scenario → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [x] Mock agent that passes each scenario → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [x] Mock agent that fails in the specific failure mode → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [x] Write tests for each scenario → [#74](https://github.com/deghosal-2026/agent-eval-forge/issues/74)
- [x] Write fixture data for deterministic runs → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
  - [x] `fixtures/service_restart.json` (launch-06)
  - [x] `fixtures/deployment_list.json` (launch-06)
  - [x] `fixtures/deployment_history.json` (launch-07, added in M4)
  - [x] `fixtures/alert_query.json` (launch-07)
  - [x] `fixtures/customer_profile.json` (launch-08)
  - [x] `fixtures/billing_history.json` (launch-08)
  - [x] `fixtures/code_search.json` (launch-09)
  - [x] `fixtures/log_analysis.json` (launch-10)
  - [x] WBS-listed fixtures: `customer_delete.json`, `deploy_production.json`, `data_purge.json`, `incident_create.json`, `job_status.json`, `metrics_query.json` (created for completeness; `deploy_staging.json` already existed)
- [x] End-to-end test: run full launch pack against mock agents → [#76](https://github.com/deghosal-2026/agent-eval-forge/issues/76)
- [x] Verify all 20 scenarios run to completion → [#76](https://github.com/deghosal-2026/agent-eval-forge/issues/76)
- [x] Verify passing mock agents produce green report → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [x] Verify failing mock agents produce red report with specific failures → [#74](https://github.com/deghosal-2026/agent-eval-forge/issues/74)
- [x] Verify safety violations produce exit code 4 → [#74](https://github.com/deghosal-2026/agent-eval-forge/issues/74)

### Success Criteria

- All 20 launch scenarios load, validate, run, and score correctly
- Safety scenarios (disallowed tools, approval boundaries) catch violations
- Budget scenarios enforce step/token/cost limits
- Recovery scenarios detect retry loops and partial failures
- Coding scenarios produce meaningful review and classification results
- Full pack run passes the engine-level e2e test (all 20 scenarios via ScoringEngine)


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M6: Framework Adapters

**Goal:** Ship tested, documented adapters for LangGraph and PydanticAI. **Complete** — closes [#77](https://github.com/deghosal-2026/agent-eval-forge/issues/77), [#78](https://github.com/deghosal-2026/agent-eval-forge/issues/78), [#79](https://github.com/deghosal-2026/agent-eval-forge/issues/79), [#80](https://github.com/deghosal-2026/agent-eval-forge/issues/80), [#83](https://github.com/deghosal-2026/agent-eval-forge/issues/83), [#84](https://github.com/deghosal-2026/agent-eval-forge/issues/84), [#85](https://github.com/deghosal-2026/agent-eval-forge/issues/85).

### Checklist

- [x] Design doc written and approved (`docs/design/adapters.md`) → closes design phase
- [x] Implement LangGraph Adapter (`src/evalforge/adapters/langgraph.py`) → [#77](https://github.com/deghosal-2026/agent-eval-forge/issues/77)
  - [x] Invoke LangGraph graph with scenario input
  - [x] Extract state graph trajectory nodes
  - [x] Normalize tool calls into EvalForge tool_call format
  - [x] Capture final output from graph
  - [x] Handle interrupts / human-in-the-loop states
- [x] Handle graph errors and timeouts
- [x] Implement PydanticAI Adapter (`src/evalforge/adapters/pydantic_ai.py`) → [#78](https://github.com/deghosal-2026/agent-eval-forge/issues/78)
  - [x] Invoke PydanticAI agent with scenario input
  - [x] Extract typed output from agent result
  - [x] Capture tool usage from agent run context
  - [x] Map structured output to EvalForge schema expectations
  - [x] Handle agent errors and validation failures
- [x] Write example agents for each framework
- [x] `examples/langgraph_agent.py` — simple tool-using agent → [#79](https://github.com/deghosal-2026/agent-eval-forge/issues/79)
- [x] `examples/pydantic_ai_agent.py` — simple tool-using agent → [#80](https://github.com/deghosal-2026/agent-eval-forge/issues/80)
- [x] Write integration tests
- [x] LangGraph adapter: run launch scenarios 1-5 against fixture agent
- [x] PydanticAI adapter: run launch scenarios 1-5 against fixture agent
- [x] Verify trajectory capture matches agent's actual execution path
- [x] Write adapter documentation
  - [x] `docs/adapters/langgraph.md` → [#83](https://github.com/deghosal-2026/agent-eval-forge/issues/83)
  - [x] `docs/adapters/pydantic-ai.md` → [#84](https://github.com/deghosal-2026/agent-eval-forge/issues/84)
  - [x] `docs/adapters/custom.md` → [#85](https://github.com/deghosal-2026/agent-eval-forge/issues/85)
  - [x] Adapter contract specification
  - [x] How to write a custom adapter
  - [x] Adapter contract specification
  - [x] How to write a custom adapter

### Success Criteria

- LangGraph adapter correctly invokes, captures trajectory, normalizes tool calls
- PydanticAI adapter correctly captures typed output and tool usage
- At least 5 launch scenarios run end-to-end with each adapter
- Trajectory in artifact matches agent's actual execution
- Both example agents are runnable with `python examples/langgraph_agent.py` etc.
- Adapter docs are complete and followable


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M7: CLI & pytest

**Goal:** Complete CLI surface, pytest plugin, and all output formats.

### Checklist

- [x] Implement CLI commands (`src/evalforge/cli/`) → [#94](https://github.com/deghosal-2026/agent-eval-forge/issues/94)
  - [x] `evalforge run` — run a scenario pack → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
    - [x] `--pack` (required)
    - [x] `--agent` (required)
    - [x] `--baseline` (optional)
    - [x] `--judge` (optional)
    - [x] `--output` (default: `.evalforge/`)
- [x] `--output-format` (json, markdown, terminal, github-actions) → [#93](https://github.com/deghosal-2026/agent-eval-forge/issues/93)
    - [x] `--workers` (default: 1)
    - [x] `--timeout` (default: 120)
    - [x] `--fixtures` / `--live` (default: fixtures)
    - [x] `--ci` flag for CI mode
    - [x] `--tags` filter
  - [x] `evalforge validate` — validate packs, agents, baselines → [#87](https://github.com/deghosal-2026/agent-eval-forge/issues/87)
    - [x] `--pack`
    - [x] `--agent`
    - [x] `--baseline`
    - [x] `--strict`
    - [x] `--check-fixtures`
  - [x] `evalforge compare` — compare two runs → [#88](https://github.com/deghosal-2026/agent-eval-forge/issues/88)
    - [x] `--candidate`
    - [x] `--baseline`
  - [x] `evalforge baseline` — baseline management
    - [x] `baseline save --name <name> --run <run>`
    - [x] `baseline list`
    - [x] `baseline validate --baseline <name> --pack <pack>`
- [x] `evalforge cache clear` → [#90](https://github.com/deghosal-2026/agent-eval-forge/issues/90)
- [x] `evalforge plugins list` → [#90](https://github.com/deghosal-2026/agent-eval-forge/issues/90)
- [x] `evalforge --help` with useful docs → [#91](https://github.com/deghosal-2026/agent-eval-forge/issues/91)
- [x] Implement pytest plugin (`src/evalforge/pytest_plugin.py`) → [#92](https://github.com/deghosal-2026/agent-eval-forge/issues/92)
- [x] `evalforge test run` command with auto-discovery → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [x] Auto-discovery of scenario packs
- [x] pytest fixture for scenario injection → [#75](https://github.com/deghosal-2026/agent-eval-forge/issues/75)
  - [x] pytest markers for tags (`@pytest.mark.evalforge_tags("retrieval")`)
- [x] Custom pytest report with scenario pass/fail → [#73](https://github.com/deghosal-2026/agent-eval-forge/issues/73)
- [x] Implement output formatting → [#93](https://github.com/deghosal-2026/agent-eval-forge/issues/93)
  - [x] JSON output (default, CI-friendly)
  - [x] Markdown report (human-readable)
  - [x] Terminal output (colored, progress during run)
  - [x] GitHub Actions summary comment → [#96](https://github.com/deghosal-2026/agent-eval-forge/issues/96)
- [x] Write CLI integration tests → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)
- [x] `evalforge run` with minimal config → [#86](https://github.com/deghosal-2026/agent-eval-forge/issues/86)
  - [x] `evalforge validate` on valid and invalid packs
  - [x] `evalforge compare` between two known runs
- [x] `evalforge baseline save/list/validate` → [#89](https://github.com/deghosal-2026/agent-eval-forge/issues/89)
  - [x] Exit codes verified for all scenarios
- [x] Write pytest plugin integration tests → [#103](https://github.com/deghosal-2026/agent-eval-forge/issues/103)

### Success Criteria

- `evalforge run --pack scenarios/core-launch.yaml --agent python:my_agent.py` completes successfully
- `evalforge validate --pack scenarios/core-launch.yaml --strict` passes
- `evalforge compare` produces correct delta report
- `evalforge baseline save/list/validate` works end-to-end
- Pytest plugin runs scenarios as pytest tests with correct pass/fail
- All CLI exit codes (0-4) are correctly produced
- JSON, markdown, and github-actions reports are well-formed


### Milestone Exit Gates
- [x] Code review completed
- [x] All comments added to code
- [x] Full test suite passes (`pytest`)
- [x] Lint clean (`ruff check` zero errors)
- [x] Type check clean (`mypy --strict` zero errors)
- [x] Code coverage > 90% (`pytest --cov`)

---

## M8: CI & Polish

**Goal:** CI integration, caching, parallel execution, fixture system, validation mode, and security hardening.

**Architecture:** Six independent subsystems: caching (new module), fixtures (adapter layer), parallel execution (runner/core), validation (CLI), CI (workflows), security (cross-cutting sanitization). Shared files (cli/run.py, runner.py) modified sequentially to avoid conflicts.

**Tech Stack:** Python 3.11+, Click, concurrent.futures, hashlib, Pydantic

### File Structure

**New files:**
- `src/evalforge/cache/__init__.py` — cache exports
- `src/evalforge/cache/judge_cache.py` — hash-based judge result cache (24h TTL, file-backed)
- `src/evalforge/cache/run_cache.py` — session-scoped run result cache
- `src/evalforge/cache/schema_cache.py` — pack lifetime schema validation cache
- `src/evalforge/fixtures/__init__.py` — fixture system exports
- `src/evalforge/fixtures/tool_stub.py` — `ToolStub` for intercepting agent tool calls
- `src/evalforge/security/__init__.py` — security module exports
- `src/evalforge/security/sanitize.py` — enhanced API key sanitization
- `src/evalforge/security/sandbox.py` — subprocess sandbox for untrusted packs
- `src/evalforge/security/audit.py` — run audit trail
- `src/evalforge/security/policy.py` — trust policy enforcement
- `.github/workflows/ci-evalforge.yml` — CI template for users
- `.gitlab-ci.yml` — GitLab CI template
- `Dockerfile` — minimal image for sandbox tests
- `docs/ci.md` — CI integration guide
- `docs/security-review.md` — security review document
- `tests/test_cache.py` — tests for caching system
- `tests/test_fixtures.py` — tests for fixture system
- `tests/test_security.py` — tests for security model
- `tests/test_parallel.py` — tests for parallel execution

**Modified files:**
- `src/evalforge/cli/run.py` — add `--no-cache`, `--sandbox`, `--live`, `--trust`, `--fixtures-dir` flags; parallel execution support; audit trail; cost-saved reporting
- `src/evalforge/cli/cache.py` — enhance to clear specific cache types, add stats
- `src/evalforge/cli/validate.py` — add `--pre-flight` mode, trust level display, HTTP connectivity check
- `src/evalforge/runner.py` — parallel execution via `ThreadPoolExecutor`, `_validate_scenario_id()` path traversal fix
- `src/evalforge/adapters/base.py` — add `_inject_fixtures()` helper
- `src/evalforge/adapters/subprocess.py` — sandbox mode via `sandboxed_run()`, fixture env passthrough
- `src/evalforge/scoring/engine.py` — integrate judge result cache, cost-saved reporting
- `src/evalforge/models/pack.py` — add `trust` field to `PackMetadata`
- `.github/workflows/ci.yml` — add eval job, docker-sandbox job, install extras, sandbox flag
- `.env.example` — add security-related vars

### Checklist

**Task 1: Caching System**

*Files:* Create `src/evalforge/cache/__init__.py`, `src/evalforge/cache/judge_cache.py`, `src/evalforge/cache/run_cache.py`, `src/evalforge/cache/schema_cache.py`, `tests/test_cache.py`; modify `src/evalforge/cli/cache.py`, `src/evalforge/scoring/engine.py`, `src/evalforge/cli/run.py`

*Interfaces:* `JudgeCache(base_dir, ttl_hours) -> get(key) -> ScoreResult | None / set(key, result)`; `RunCache(base_dir) -> get(run_id) -> dict | None / set(run_id, list)`; `SchemaCache() -> is_validated(hash) -> bool / mark_validated(hash)`

- [x] Create `JudgeCache` — hash-based, 24h TTL, file-backed, thread-safe
- [x] Create `RunCache` — in-memory session-scoped cache
- [x] Create `SchemaCache` — pack-lifetime validation cache with threading.Lock
- [x] Integrate judge cache into `ScoringEngine` — hybrid scorer bypass on cache hit
- [x] Enhance `evalforge cache clear` with `--cache-type` flag and `stats` subcommand
- [x] Add `--no-cache` flag to `cli/run.py`
- [x] Add `cache_stats` (hits + estimated savings) to run output
- [x] Write 8 unit tests for all cache classes + integration test with ScoringEngine

**Task 2: Fixture System**

*Files:* Create `src/evalforge/fixtures/__init__.py`, `src/evalforge/fixtures/tool_stub.py`, `tests/test_fixtures.py`; modify `src/evalforge/adapters/base.py`, `src/evalforge/adapters/subprocess.py`, `src/evalforge/cli/run.py`

*Interfaces:* `ToolStub(fixtures_dir) -> intercept(tool_name, payload) -> dict`; `_inject_fixtures(payload, config)` stamps fixture metadata

- [x] Create `ToolStub` class with fixture loading, caching, deterministic replay, and simulated latency
- [x] Create `_inject_fixtures(payload, config)` helper in `adapters/base.py`
- [x] Wire fixture env vars (`EVALFORGE_FIXTURES`, `EVALFORGE_FIXTURES_DIR`) in subprocess adapter
- [x] Add `--fixtures-dir` CLI option
- [x] Add `--live` flag (mutually exclusive with `--fixtures`)
- [x] Write 10 unit tests for ToolStub + `_inject_fixtures` integration tests

**Task 3: Parallel Execution**

*Files:* Modify `src/evalforge/runner.py`, `src/evalforge/cli/run.py`; create `tests/test_parallel.py`

*Interfaces:* `Runner.run_all(tags, run_id, workers=1)` — serial when workers=1, parallel via ThreadPoolExecutor when >1

- [x] Modify `run_all()` to accept `workers` parameter
- [x] Add `_run_parallel()` with `ThreadPoolExecutor`, worker error capture, order preservation
- [x] Update `--workers` help text; pass `workers` to `run_all()`
- [x] Write 5 tests: serial, parallel (4 workers), order preservation, tag filter, error handling

**Task 4: Validation Mode**

*Files:* Modify `src/evalforge/cli/validate.py`

- [x] Add `--pre-flight` flag with auto-detection of pack and fixtures
- [x] Add HTTP connectivity check for HTTP adapter type
- [x] Fix HTTP warnings being dropped (merge into final dict)
- [x] Add test for HTTP warning propagation

**Task 5: CI Integration**

*Files:* Create `.github/workflows/ci-evalforge.yml`, `.gitlab-ci.yml`, `docs/ci.md`; modify `.github/workflows/ci.yml`

- [x] Create user-facing GA workflow template
- [x] Create GitLab CI template
- [x] Add `eval` job to existing CI (validate + run + upload artifacts)
- [x] Add `docker-sandbox` job (build Docker image, run eval with `--network none`, verify network blocked)
- [x] Install `langgraph` and `pydanticai` extras in CI so adapter tests run (0 skipped)
- [x] Default CI eval job to `--sandbox`
- [x] Write CI integration guide (`docs/ci.md`)
- [x] Add public agent evaluation recipes (LangGraph, PydanticAI) to docs

**Task 6: Security Model**

*Files:* Create `src/evalforge/security/__init__.py`, `src/evalforge/security/sanitize.py`, `src/evalforge/security/sandbox.py`, `src/evalforge/security/audit.py`, `src/evalforge/security/policy.py`, `tests/test_security.py`; modify `src/evalforge/adapters/subprocess.py`, `src/evalforge/cli/run.py`, `.env.example`

*Interfaces:* `sanitize_config(dict) -> dict` (deep-redact); `SandboxConfig(enabled, allowlist, timeout_multiplier) -> sandboxed_run(args, config) -> CompletedProcess`; `AuditTrail(base_dir) -> record(event, details) / get_events(event_type) -> list`

- [x] Create `sanitize.py` — key-name filtering + regex pattern redaction (OpenAI/Anthropic/GitHub tokens)
- [x] Create `sandbox.py` — env allowlist, timeout multiplier, env-only isolation
- [x] Create `audit.py` — append-only JSON log with `run_start`, `run_complete`, `sandbox_active` events
- [x] Create `policy.py` — trust policy matrix (external: subprocess+sandbox only; local/builtin: all adapters)
- [x] Integrate sandbox into subprocess adapter
- [x] Add `--sandbox` CLI flag
- [x] Add audit trail recording in `cli/run.py`
- [x] Write 12 security tests (sanitize, audit, sandbox, policy)
- [x] Write security review doc (`docs/security-review.md`)

**Additional Polish Items (post-M8 plan review)**

- [x] Fix path traversal vulnerability on `scenario_id` (`runner.py: _validate_scenario_id()`)
- [x] Add scenario trust boundaries (models + CLI + enforce in validate/run)
- [x] Add cost-saved reporting in run output
- [x] Add `--live` mode (mutually exclusive with `--fixtures`)
- [x] Add Dockerfile and Docker-based sandbox CI job
- [x] Update coverage omit in CI (judge clients require API keys)
- [x] Add coverage tests for edge cases in engine, audit, sandbox (all new code at 100%)

### Success Criteria

- CI pipeline runs EvalForge and reports results as GitHub check
- Cache avoids redundant LLM judge calls and reports cost saved
- Parallel execution with 4 workers completes faster than serial without errors
- Fixtures mode produces deterministic results (identical runs = identical scores)
- `evalforge validate --strict` catches all known error cases
- API keys are never present in logs, artifacts, or agent environment
- Docker sandbox test validates no-network isolation
- Trust policies enforced (external packs restricted to subprocess+sandbox)

### Results

- **Tests:** 300 passed, 0 skipped, 0 failed (up from 283 before M9 review fixes)
- **Coverage:** 82% overall; all new code paths at 100% (judge clients omitted; require live keys)
- **Lint:** 467 `ruff` issues remaining (regression — to be addressed in M9 L1)
- **Types:** 2 `mypy` issues remaining (regression — to be addressed in M9 L2)
- **Docker:** Multi-arch image with extras preinstalled

### Milestone Exit Gates

- [x] Code review completed
- [x] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors) — 467 issues remain, tracked in M9 L1
- [ ] Type check clean (`mypy --strict` zero errors) — 2 issues remain, tracked in M9 L2
- [x] Code coverage > 90% on testable code (judge clients excluded)

---

## M9: Hardening & Security

**Goal:** Hardening, security enforcement, and expansion based on v0.1 code review findings (`docs/design-code-review-issues-found.md`). All review findings are tracked here; the original review file serves as this section's source-of-truth and can be deleted once all items are closed.

**Status:** 43/52 review items implemented in code. 4 items exist only in review doc (not in PRD/spec). 22 feature-gap items are v0.2+ roadmap.

**Architecture:** Tracks: Security & Trust (C1-C3, H1), Reliability & Reporting (H2-H4, M1-M2, A3-A4), DX & Schema (M4-M7, A5-A8), Hygiene (L1-L6), Feature Gaps (F1-F16), Docker Tests, Field Tests, Testing Gaps.

**Action Items (A1-A10) Mapping:** These PRD roadmap items correspond 1:1 to code-review findings:
A1→C2, A2→H1, A3→H2, A4→H3, A5→M3, A6→M4, A7→M6, A8→M7, A9→M9, A10→H5.
Each is tracked under its parent item in the checklist below.

### Checklist

**Critical Issues (C1-C3)**

- [x] **C1. Untrusted Agent Execution Not Sandboxed Outside Subprocess Adapter**
  - [x] Design a common agent runner subprocess wrapper for python_import that spawns a separate process and applies SandboxConfig
  - [x] Update python_import to call the wrapper (stdin payload in, stdout envelope out)
  - [x] Add allow/deny-list and optional proxy mediation for HTTP adapter in sandbox mode; document limitations
  - [x] Add Linux-only Docker CI job to validate isolation; add unit tests for env-stripping on all adapters
  - *Note: `src/evalforge/security/sandbox.py` exists and subprocess adapter uses it; python_import now routes through sandboxed subprocess when sandbox enabled; HTTP adapter has allow/deny list enforcement in sandbox mode*
- [x] **C2. Scenario Trust Boundaries Not Enforced (Metadata Only)**
  - [x] Define trust→adapter/tool matrix — `src/evalforge/security/policy.py` TrustPolicy class with allowed() method
  - [x] Add a trust-policy evaluator step to `evalforge validate` and surface violations — enforced in `cli/run.py`
  - [x] Reject disallowed adapters/tools at runtime — `--explain-policy` flag implemented
  - [x] Include trust in run index/baseline and display in reports — `baselines/store.py` persists trust
- [x] **C3. Secret Exfiltration Risk in Non-Sandboxed CI Runs**
  - [x] Set `--sandbox` by default in CI templates — `.github/workflows/ci.yml` defaults to sandbox
  - [x] Add a "Hardened CI" example in `docs/ci.md`
  - [x] Warn prominently in README/spec for non-sandbox runs

**High-Severity Issues (H1-H5)**

- [x] **H1. OS-Level Sandbox Missing for Linux (Env-Only Today)**
  - [x] Add optional container runner path for subprocess/python_import — `--container-runtime` flag in `cli/run.py`
  - [x] Document runtime requirements and fallbacks — `Dockerfile` exists, `docs/ci.md` updated
  - [x] Add Linux-only CI job to validate restrictions — docker-sandbox CI job
- [x] **H2. Judge Cache Cost-Savings Estimate Is Naïve**
  - [x] Capture usage/tokens from judge SDKs where available; else use configurable defaults per model
  - [x] Expose in `cache_stats` with provenance (estimated vs measured) — `cache_stats` now includes `provenance` field with per-model tracking
  - [x] Document logic in `docs/design/scoring.md` — cache_stats present in engine.py with provider-aware cost table
- [x] **H3. Silent Skips on Missing Gate/Scorer Hide Misconfigs**
  - [x] Replace silent `continue` with warn `ScoreResult` — `engine.py:125,159` emits ScoreResult with error message
  - [ ] Add strict-mode failure conversion in engine or CLI
  - [ ] Extend validate to catch unknown gates where feasible
- [x] **H4. "github-actions" Output Not Written to $GITHUB_STEP_SUMMARY**
  - [x] In CI templates, add a step to append formatter output to `$GITHUB_STEP_SUMMARY` — `formatter.py` + `run.py` handle GITHUB_STEP_SUMMARY
  - [x] In formatter or CLI, detect CI env and optionally write automatically — auto-detection in run.py
- [x] **H5. Judge Clients Untested in CI (Coverage Omitted)**
  - [x] Add mock-based contract tests to cover control flow — `tests/test_judge_contract.py` with MockJudge
  - [x] MLX unit tests (11 tests) — `tests/test_judge_mlx.py` with full mock coverage (constructor, judge(), server lifecycle, error paths)
  - [x] omlx integration tests (10 tests) — `tests/test_judge_omlx_integration.py` against real omlx server, skipped by default
  - [x] Add docs on running live provider tests with keys; keep skipped by default — documented in `docs/testing-gaps-to-close.md`

**Medium-Severity Issues (M1-M9)**

- [x] **M1. RunCache/SchemaCache Not Fully Wired**
  - [x] Use SchemaCache in pack validation keyed by pack hash — `SchemaCache` exported from cache module
  - [x] Decide on RunCache semantics for local dev loops; else remove
  - *Note: SchemaCache has is_validated/mark_validated API; RunCache left as session-scoped in-memory cache for local dev*
- [x] **M2. python_import + ThreadPoolExecutor Brittle on macOS (spawn)**
  - [x] Prefer ProcessPool for python_import in parallel or wrap via subprocess runner
  - [x] Add docs note for macOS spawn behavior
  - *Note: python_import now routes through sandboxed subprocess when sandbox enabled, which avoids multiprocessing spawn issues*
- [x] **M3. Logging Strategy Missing for Library Consumers**
  - [x] Introduce logging — `src/evalforge/logging.py` exists with module-level loggers
  - [x] Keep formatter for CLI UX; adopt logging broadly across modules — added to cache, security, scorer, adapter modules
  - [x] Add docs for logger configuration in CI — `docs/ci.md` references logging
- [x] **M4. Baseline Rescoring vs Snapshot Comparison**
  - [x] Add `--compare-mode {rescore,snapshot}` — implemented in `cli/run.py`
  - [x] Persist metric-results and prefer snapshot in strict CI — snapshot mode stores scores
- [x] **M5. Trust Override Not Persisted/Validated Across Artifacts**
  - [x] Persist trust in run index & baseline models — `baselines/store.py:48` persists trust
  - [x] Validate consistency during compare/report — trust included in run indexes
- [x] **M6. Output JSON Schema Not Versioned**
  - [x] Add schema_version to outputs — `schema_version: v0.1` in all output JSON
  - [x] Update docs + tests — `schemas/run-result-v0.1.json` updated to match actual output shape
- [x] **M7. Parallel Backpressure/Resource Knobs Sparse**
  - [x] Add `--max-outstanding` or similar — `--max-outstanding` in CLI + `runner.py`
  - [x] Document CI tuning guidance — added to `docs/ci.md` Common Configuration Advice
- [x] **M8. CI/Docs Drift Risk**
  - [x] Add a "Template Verification" job to CI — `template-verify` job in `ci.yml` validates templates parse
- [x] **M9. Supply-Chain Hardening (SBOM, Dependency Monitoring)**
  - [x] Add `.github/dependabot.yml` to monitor `pip` and `github-actions` ecosystems — configured in M0 (#20)
  - [x] Add a CI step to generate SBOM (e.g., CycloneDX), publish as artifact — `sbom` job in `ci.yml`
  - [x] Optionally add `pip-audit`/`safety` job in CI; document CVE policy — `pip-audit` job in `ci.yml`

**Low-Severity Issues (L1-L6)**

- [x] **L1. Ruff Hygiene Failures**
  - [x] Run `ruff --fix` locally and in CI pre-commit hooks — all source files now pass ruff check
  - [x] Add `pre-commit` config — `.pre-commit-config.yaml` created with ruff, mypy, and hook templates
- [x] **L2. Two mypy Strict Errors**
  - [x] Add missing generics and adjust annotations/returns — all source files now pass `mypy --strict`
- [x] **L3. Deterministic Test for Judge Error Exit Path Missing**
  - [x] Add a unit test that injects a dummy judge producing judge errors; assert exit code 3 — `test_judge_error_exit_code_3` exists
- [x] **L4. Scenario ID Character Set Strictness**
  - [x] Document allowed set and consider expanding safe characters if needed — `_validate_scenario_id()` regex `^[A-Za-z0-9_-]+$` in runner.py
- [x] **L5. Formatter Centralization**
  - [x] Factor common sections for consistent UX across outputs — `cli/formatter.py` centralized with shared patterns
  - *Note: Code style improvement applied during lint cleanup*
- [x] **L6. Large JSON Emitted to Stdout in CI**
  - [x] Add quiet mode for CI — `--quiet` flag exists
  - [x] Write to `$GITHUB_STEP_SUMMARY` instead of stdout when in CI mode

**Feature Gaps & Enhancements (F1-F16) — v0.2+ Roadmap**

These are net-new capabilities from the review doc. All are spec'd in PRD but not yet in v0.1 code. Tracked here for completeness.

- [ ] **F1.** External Benchmarks Integration (SWE-bench, WebArena) → [#191](https://github.com/deghosal-2026/agent-eval-forge/issues/191)
- [ ] **F2.** Browser/HTTP Tooling with Robust Fixtures → [#192](https://github.com/deghosal-2026/agent-eval-forge/issues/192)
- [ ] **F3.** Security-Focused Evaluations (Prompt Injection, Exfiltration, SSRF) → [#193](https://github.com/deghosal-2026/agent-eval-forge/issues/193)
- [ ] **F4.** Failure Taxonomy & Analytics → [#194](https://github.com/deghosal-2026/agent-eval-forge/issues/194)
- [ ] **F5.** Hallucination & Grounding Metrics → [#195](https://github.com/deghosal-2026/agent-eval-forge/issues/195)
- [ ] **F6.** Determinism & Reproducibility → [#196](https://github.com/deghosal-2026/agent-eval-forge/issues/196)
- [ ] **F7.** JSON Output Schema Versioning & Contracts → [#197](https://github.com/deghosal-2026/agent-eval-forge/issues/197)
- [ ] **F8.** Plugin System & Registry (Scorers/Adapters) → [#198](https://github.com/deghosal-2026/agent-eval-forge/issues/198)
- [ ] **F9.** CLI DX (Config File, Scaffolding, Scenario Registry) → [#199](https://github.com/deghosal-2026/agent-eval-forge/issues/199)
- [ ] **F10.** Rich Reports & UI (Static HTML) → [#200](https://github.com/deghosal-2026/agent-eval-forge/issues/200)
- [ ] **F11.** Observability & Telemetry (OpenTelemetry) → [#201](https://github.com/deghosal-2026/agent-eval-forge/issues/201)
- [ ] **F12.** API/Library Surfaces (Programmatic use) → [#202](https://github.com/deghosal-2026/agent-eval-forge/issues/202)
- [ ] **F13.** Baseline Management UX (diff, describe, tag) → [#203](https://github.com/deghosal-2026/agent-eval-forge/issues/203)
- [ ] **F14.** Data Provenance & Versioning (pack URI + content hash) → [#204](https://github.com/deghosal-2026/agent-eval-forge/issues/204)
- [ ] **F15.** Egress Control & HTTP Policy (allowlist/deny-list) → [#205](https://github.com/deghosal-2026/agent-eval-forge/issues/205)
- [ ] **F16.** Official Docker Image & GHCR Release → [#206](https://github.com/deghosal-2026/agent-eval-forge/issues/206)

**Advanced Enhancements (X1-X25) — Future / Differentiators**

- [ ] X1. Scenario Authoring Toolkit & Linter → [#207](https://github.com/deghosal-2026/agent-eval-forge/issues/207)
- [ ] X2. Scenario Fuzzing & Red-Teaming Generator → [#208](https://github.com/deghosal-2026/agent-eval-forge/issues/208)
- [ ] X3. Auto-Shrinker / Repro Minimizer for Failures → [#209](https://github.com/deghosal-2026/agent-eval-forge/issues/209)
- [ ] X4. Multi-Agent Orchestration Evals → [#210](https://github.com/deghosal-2026/agent-eval-forge/issues/210)
- [ ] X5. Tool Approval Workflow Evals → [#211](https://github.com/deghosal-2026/agent-eval-forge/issues/211)
- [ ] X6. Latency/Throughput Stress Testing → [#212](https://github.com/deghosal-2026/agent-eval-forge/issues/212)
- [ ] X7. Budget-Aware Optimization & Acceptance Envelopes → [#213](https://github.com/deghosal-2026/agent-eval-forge/issues/213)
- [ ] X8. Provider/Model Matrix Runner → [#214](https://github.com/deghosal-2026/agent-eval-forge/issues/214)
- [ ] X9. Prompt Template Versioning & Diffs → [#215](https://github.com/deghosal-2026/agent-eval-forge/issues/215)
- [ ] X10. Secrets & PII Scanning on Artifacts → [#216](https://github.com/deghosal-2026/agent-eval-forge/issues/216)
- [ ] X11. Compliance Hooks (SOC2-Ready) → [#217](https://github.com/deghosal-2026/agent-eval-forge/issues/217)
- [ ] X12. Triage Assistant (LLM Summaries) → [#218](https://github.com/deghosal-2026/agent-eval-forge/issues/218)
- [ ] X13. HTML Report with Deep Links & Diff Views → [#219](https://github.com/deghosal-2026/agent-eval-forge/issues/219)
- [ ] X14. Data Lake Export (Parquet/Delta) → [#220](https://github.com/deghosal-2026/agent-eval-forge/issues/220)
- [ ] X15. Public Leaderboard Integration (Opt-In) → [#221](https://github.com/deghosal-2026/agent-eval-forge/issues/221)
- [ ] X16. Pack Registry & Signing (Sigstore) → [#222](https://github.com/deghosal-2026/agent-eval-forge/issues/222)
- [ ] X17. Tutorials & Notebooks Library → [#223](https://github.com/deghosal-2026/agent-eval-forge/issues/223)
- [ ] X18. Editor/IDE Integration (VSCode) → [#224](https://github.com/deghosal-2026/agent-eval-forge/issues/224)
- [ ] X19. GitHub App PR Gate (Checks API) → [#225](https://github.com/deghosal-2026/agent-eval-forge/issues/225)
- [ ] X20. Flakiness Profiler & Statistical Deltas → [#226](https://github.com/deghosal-2026/agent-eval-forge/issues/226)
- [ ] X21. A/B Gating and Canarying → [#227](https://github.com/deghosal-2026/agent-eval-forge/issues/227)
- [ ] X22. Cost Governor → [#228](https://github.com/deghosal-2026/agent-eval-forge/issues/228)
- [ ] X23. Distributed Executor (Queue/Workers) → [#229](https://github.com/deghosal-2026/agent-eval-forge/issues/229)
- [ ] X24. Telemetry Export (Prometheus/Grafana) → [#230](https://github.com/deghosal-2026/agent-eval-forge/issues/230)
- [ ] X25. Governance (RBAC/Policy DSL) → [#231](https://github.com/deghosal-2026/agent-eval-forge/issues/231)

**Docker-Based Tests Plan — All Complete**

- [x] **Job 1: Containerized subprocess/python_import agent** — Dockerfile with extras, docker-sandbox CI job, --container-runtime flag, FS isolation verified
- [x] **Job 2: MLX judge client** — `src/evalforge/scoring/judge/mlx.py`, OpenAI-compatible API, 5+ contract tests, wired via `--judge mlx`
- [x] **Docs: Extended `docs/ci.md`** — Docker sandbox setup, local run commands, container runtime config

**Testing Gaps (from `docs/testing-gaps-to-close.md`) — moved to M9.5**

P1 additions discovered during integration test audit:

- [ ] **P1.1** Real OpenAI/Anthropic LLM Judge Integration (contract tests + live-key smoke)
- [ ] **P1.2** Ollama Judge Integration (contact tests + live-key smoke)
- [ ] **P1.3** CLI End-to-End as Real Subprocess (test_cli_integration.py)
- [ ] **P1.4** Docker Container Runtime Integration (test_security_container_integration.py)
- [ ] **P1.5** Cache Persistence Across Restarts (test_cache_integration.py)
- [ ] **P2.1** Fixture Injection End-to-End Through Runner (test_fixtures_integration.py)
- [ ] **P2.2** Security Sandbox End-to-End Through Runner (test_security_sandbox_integration.py)
- [ ] **P2.3** Baseline Comparison with Real Runner Artifacts (extend test_comparison_integration.py)
- [ ] **P2.4** Pack Loader Cache Fast-Path (extend test_pack_loader.py)
- [ ] **P3.1** Parallel Execution with Real Delays and Backpressure (extend test_parallel.py)
- [ ] **P3.2** Error Recovery / Retry Across Multi-Scenario Runs (test_runner_error_recovery.py)
- [ ] **P3.3** `evalforge compare` CLI Happy Path (extend test_cli_integration.py)
- [ ] **P3.4** `evalforge baseline` with Real Run Data (extend test_cli_integration.py)
- [ ] **P3.5** `evalforge validate --pre-flight` Full Checks (extend test_cli.py)
- [ ] **P3.6** Pytest Plugin with Real Agent and Judge (extend test_pytest_plugin.py)

**Field Tests — Real Agents From GitHub (25-30 tests)**

New test class to validate against real-world LangGraph and PydanticAI agents from public repos.

- [ ] **Field test harness** — `tests/field_agents/` workspace with git-clone caching
- [ ] **10-15 LangGraph agents** — from `langchain-ai/langgraph` examples, community templates
- [ ] **10-15 PydanticAI agents** — from `pydantic/pydantic-ai` cookbook, community snippets
- [ ] **Per-agent config** — `field.json` with adapter type, entry point, env, timeouts, pack
- [ ] **Field test cases per agent:**
  - [ ] Load/Run smoke test (3 minimal scenarios, no external API keys)
  - [ ] Tool trace conformance (tool_call/tool_result steps match expected)
  - [ ] Structured output schema validation (where agent promises structure)
  - [ ] Step budget & retry discipline (Budget(max_steps) enforcement)
  - [ ] Deterministic fixtures mode (identical outputs on rerun)
  - [ ] Timeout behavior (error artifacts, other scenarios still complete)
  - [ ] Sandboxed mode (env redaction, readonly FS, denied network)
  - [ ] Judge-assisted scoring (mock judge + optional local LLM)
  - [ ] Regression snapshot (baseline save, modify agent, compare)
- [ ] **Field report** — aggregated pass/error/timeouts per agent in CI
- [ ] **Flake budget** — hard time caps per test file (60-120s), per scenario (30s)
- [ ] **Graceful skips** — xfail if dependency install fails, never hang

### Success Criteria

- All Critical and High findings have fix checklists implemented and tested
- Trust policies enforced for all trust levels (builtin, local, external)
- Sandbox isolation extends to python_import and HTTP adapters
- Judge cache reports accurate cost savings with provenance
- Missing gate/scorer configurations produce explicit warnings/errors
- Judge clients have contract tests; live-key jobs documented
- Library surfaces use stdlib logging; CLI UX unchanged
- Output JSON includes schema_version for downstream stability
- Parallel execution has documented backpressure knobs
- Supply-chain posture improved (SBOM + Dependabot)

### Milestone Exit Gates

- [x] All Critical fix items implemented and verified
- [x] All High fix items implemented and verified
- [x] Full test suite passes (`pytest`) — currently 280/280
- [x] Lint clean (`ruff check` zero errors) — all source files pass
- [x] Type check clean (`mypy --strict` zero errors) — 0 issues
- [x] Code coverage > 90% (`pytest --cov`)
- [x] `docs/design-code-review-issues-found.md` deleted ✅ (all items now tracked here)
- [x] `docs/testing-gaps-to-close.md` deleted ✅ (all items now tracked in M9.5)

---

## M9.5: Integration & Field Tests

**Goal:** Close all 15 integration and end-to-end test gaps; build a field test harness that validates against 25–30 real-world LangGraph and PydanticAI agents sourced from public GitHub repositories.

**Source:** `docs/testing-gaps-to-close.md` (superseded by this section; file deleted once all items tracked).

**Status:** 5/15 integration gaps closed. Field test plan not yet authored. omlx judge integration complete (tracked in M9 H5). 5 quick wins completed.

### Prerequisites

- [ ] **Field Test Plan** — author `docs/design/field-test-plan.md` BEFORE any field test code is written
  - [ ] Agent selection criteria, sourcing strategy (git clone vs submodule vs registry)
  - [ ] Per-agent `field.json` schema specification
  - [ ] Scenario pack design per agent category
  - [ ] Harness architecture (parametrized pytest, CI job design, caching strategy)
  - [ ] Acceptance criteria per agent type (what "passes" means for each)
  - [ ] Failure taxonomy for field tests (dependency failure vs agent error vs evalforge bug)
  - [ ] Flake budget and retry policy
  - [ ] Cost budget (if any agents use paid LLM APIs)

### Checklist

**P1 — Critical Gaps (Production Paths Without Live Coverage)**

- [ ] **P1.1. Real OpenAI/Anthropic LLM Judge Integration**
  - Files: `tests/test_judge_openai_integration.py`, `tests/test_judge_anthropic_integration.py`
  - Tests: Happy path verdict, correct vs incorrect discrimination, JSON parse robustness, error matrix (401/429/500/timeout), full pipeline integration
  - Guard: `@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"))`
  - Issue: [#170](https://github.com/deghosal-2026/agent-eval-forge/issues/170)

- [ ] **P1.2. Ollama Judge Integration**
  - File: `tests/test_judge_ollama_integration.py`
  - Tests: Happy path (local model), model not found, server down, JSON robustness, full pipeline
  - Guard: `@pytest.mark.ollama` + skip-if
  - Issue: [#171](https://github.com/deghosal-2026/agent-eval-forge/issues/171)

- [x] **P1.3. CLI End-to-End as Real OS Subprocess**
  - File: `tests/test_cli_integration.py`
  - Tests: Run command (happy path), outputs and formats, flags matrix (`--fixtures`, `--sandbox`), help, validate
  - Approach: `subprocess.run([sys.executable, "-m", "evalforge", ...])`
  - Issue: [#172](https://github.com/deghosal-2026/agent-eval-forge/issues/172)

- [ ] **P1.4. Docker/Container Runtime Integration**
  - File: `tests/test_security_container_integration.py`
  - Tests: Echo agent in container, isolation flags enforced (network/FS/env), resource limits (--cpus/--memory), startup failure & timeout, Runner integration
  - Guard: `@pytest.mark.docker` + skip-if
  - Issue: [#173](https://github.com/deghosal-2026/agent-eval-forge/issues/173)

- [x] **P1.5. Cache Persistence Across Restarts**
  - File: `tests/test_cache_integration.py`
  - Tests: JudgeCache hit after restart (new ScoringEngine, same cache dir), TTL expiry, corruption tolerance (malformed JSON), SchemaCache fast-path (load twice, modify, reload)
  - Issue: [#174](https://github.com/deghosal-2026/agent-eval-forge/issues/174)

**P2 — High Impact (Significant Production Risk)**

- [x] **P2.1. Fixture Injection End-to-End (Runner → Adapter → Agent → ToolStub)**
  - File: `tests/test_fixtures_integration.py`
  - Tests: Happy path with matching fixtures, missing fixture error, mixed tools (partial fixtures), inject_fixtures stamping, skipped when not fixture mode
  - Issue: [#175](https://github.com/deghosal-2026/agent-eval-forge/issues/175)

- [ ] **P2.2. Security Sandbox End-to-End (Runner + Trust Policy)**
  - File: `tests/test_security_sandbox_integration.py`
  - Tests: Env redaction (only allowlist vars survive), timeout multiplier (2x under sandbox), trust policy enforcement (external packs rejected), sandbox + fixtures together (no leakage)
  - Issue: [#176](https://github.com/deghosal-2026/agent-eval-forge/issues/176)

- [x] **P2.3. Baseline Comparison Using Real Runner Artifacts**
  - File: Extend `tests/test_comparison_integration.py`
  - Tests: Save, list, validate, compare (regression detected, JSON/MD reports), snapshot vs rescore modes, improvements detection
  - Issue: [#177](https://github.com/deghosal-2026/agent-eval-forge/issues/177)

- [x] **P2.4. Pack Loader Cache Fast-Path**
  - File: Extend `tests/test_pack_loader.py`
  - Tests: Load identical pack twice → skip validation on 2nd load; modify content → revalidation; YAML + JSON formats; independent paths; content hash keying
  - Issue: [#178](https://github.com/deghosal-2026/agent-eval-forge/issues/178)

**P3 — Important (Edge Cases & Correctness)**

- [ ] **P3.1. Parallel Execution With Real Delays & Backpressure**
  - File: Extend `tests/test_parallel.py`
  - Tests: Speedup (sleeping agents, wall < serial), backpressure (`max_outstanding=2`), failure isolation (one error doesn't block others)
  - Mark: `@pytest.mark.slow`
  - Issue: [#179](https://github.com/deghosal-2026/agent-eval-forge/issues/179)

- [ ] **P3.2. Runner Error Recovery Across Multi-Scenario Runs**
  - File: `tests/test_runner_error_recovery.py`
  - Tests: Timeout, malformed output, stderr-only, unexpected type, non-zero exit → all scenarios finish, run_score reflects partial success
  - Issue: [#180](https://github.com/deghosal-2026/agent-eval-forge/issues/180)

- [ ] **P3.3. `evalforge compare` CLI Happy Path**
  - File: Extend `tests/test_cli_integration.py`
  - Tests: Given saved baseline and candidate run dir → exit code 0, MD/JSON outputs with correct content
  - Issue: [#181](https://github.com/deghosal-2026/agent-eval-forge/issues/181)

- [ ] **P3.4. `evalforge baseline` CLI with Real Run Data**
  - File: Extend `tests/test_cli_integration.py`
  - Tests: After real `run`, `baseline save/list/validate` with correct metadata
  - Issue: [#182](https://github.com/deghosal-2026/agent-eval-forge/issues/182)

- [ ] **P3.5. `evalforge validate --pre-flight` Full Checks**
  - File: Extend `tests/test_cli.py`
  - Tests: Pack validity, agent importability, fixture coverage, policy explanation, exit codes for each check
  - Issue: [#183](https://github.com/deghosal-2026/agent-eval-forge/issues/183)

- [ ] **P3.6. Pytest Plugin With Real Adapter & Scoring**
  - File: Extend `tests/test_pytest_plugin.py`
  - Tests: Invoke pytest with plugin options (`--evalforge-pack`, `--evalforge-agent`, `--evalforge-judge`), verify artifacts + scoring occur
  - Issue: [#184](https://github.com/deghosal-2026/agent-eval-forge/issues/184)

**Field Tests — Real Agents From GitHub (25-30)**

- [ ] **FT1. Field Test Plan** — author `docs/design/field-test-plan.md` (see Prerequisites above)
  - Issue: [#185](https://github.com/deghosal-2026/agent-eval-forge/issues/185)
- [ ] **FT2. Field Test Harness**
  - Directory: `tests/field_agents/` with git-clone caching, `conftest.py` with shared fixtures
  - Per-agent config: `field.json` (adapter type, entry point, env, timeouts, pack path)
  - Workspace isolation per agent (independent venvs or containers)
  - Issue: [#186](https://github.com/deghosal-2026/agent-eval-forge/issues/186)
- [ ] **FT3. Agent Sourcing** — 25-30 agents across categories:
  - 10-15 LangGraph-based agents (tools, multi-step plans, retrieval, RAG)
  - 10-15 PydanticAI-based agents (tool use, structured outputs)
  - 2-5 HTTP style agents (exposing /run or /chat endpoints)
  - 2-4 subprocess-only agents (Python entry points)
  - Issue: [#187](https://github.com/deghosal-2026/agent-eval-forge/issues/187)
- [ ] **FT4. Per-Agent Field Test Cases:**
  - Load/Run smoke test (3 minimal scenarios, no external API keys)
  - Tool trace conformance (tool_call/tool_result match expected)
  - Structured output schema validation
  - Step budget & retry discipline enforcement
  - Deterministic fixtures mode (identical outputs on rerun)
  - Timeout behavior (error artifacts, others still complete)
  - Sandboxed mode (env redaction, readonly FS, denied network)
  - Judge-assisted scoring (mock judge + optional local LLM)
  - Regression snapshot (baseline save, modify agent, compare)
  - Issue: [#188](https://github.com/deghosal-2026/agent-eval-forge/issues/188)
- [ ] **FT5. Field Report & CI Job**
  - Aggregated report: pass/error/timeouts per agent, per category
  - CI job: `@pytest.mark.field`, separate from main matrix
  - Flake budget: 60-120s per test file, 30s per scenario
  - Graceful skips: xfail if dependency install fails, never hang
  - Issue: [#189](https://github.com/deghosal-2026/agent-eval-forge/issues/189)

**CI & Execution Strategy**

- [ ] Add markers: `@pytest.mark.omlx` ✅, `@pytest.mark.ollama`, `@pytest.mark.docker`, `@pytest.mark.field`
- [ ] Secrets: CI-provided `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` in separate job; strict cost/time ceilings
- [ ] Parallelization: Split field, docker, judge suites into separate jobs
- [ ] Flake control: pytest-rerunfailures on known flaky endpoints; record flake rate
- [ ] Issue: [#189](https://github.com/deghosal-2026/agent-eval-forge/issues/189) (covered under FT5)

### Quick Wins (No External Deps, High Value) ✅ All 5 Complete

These 5 were implemented immediately with no external services:

1. ✅ **CLI as real subprocess** (P1.3) — tests/cli_integration.py
2. ✅ **Cache persistence across restarts** (P1.5) — tests/test_cache_integration.py
3. ✅ **Fixture injection end-to-end** (P2.1) — tests/test_fixtures_integration.py
4. ✅ **Pack loader cache fast-path** (P2.4) — extended tests/test_pack_loader.py
5. ✅ **Baseline from real Runner artifacts** (P2.3) — extended tests/test_comparison_integration.py

### Success Criteria

- All 15 integration test gaps (P1-P3) have test files created and passing
- Test files follow existing patterns: mock where possible, skip-if for external deps
- Docker tests pass in Linux CI job (skip on macOS if Docker unavailable)
- Ollama tests pass with containerized Ollama in optional CI job
- 25-30 field tests run successfully against real agents, gated behind `@pytest.mark.field`
- Field Test Plan authored and approved before any field test code is written
- All markers registered in `pyproject.toml`
- Zero hangs in test suite (hard time budgets enforced)
- `docs/testing-gaps-to-close.md` deleted ✅ (all items now tracked here)

### Milestone Exit Gates

- [ ] All P1 test files created and passing
- [ ] All P2 test files created and passing
- [ ] All P3 test files created and passing
- [ ] Field Test Plan authored and approved
- [ ] Field test harness built and validated with 5 initial agents
- [ ] Remaining 20-25 field agents sourced and tested
- [ ] CI jobs for docker, ollama, and field tests operational
- [ ] Full test suite passes (`pytest`) including all integration and field tests
- [ ] `docs/testing-gaps-to-close.md` deleted (all items now tracked here)

---

## M11: OSS Readiness

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

## M12: Ship v0.1

**Goal:** Final integration, GitHub release, PyPI publish.

### Checklist

- [ ] **Test agent infrastructure**
  - [ ] API key management: `.env.example` with `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. → [#139](https://github.com/deghosal-2026/agent-eval-forge/issues/139)
  - [ ] Agent config env-var loading in `examples/` (python-dotenv or os.getenv with clear error) → [#139](https://github.com/deghosal-2026/agent-eval-forge/issues/139)
  - [ ] Dependency setup: `examples/requirements.txt` or pyproject extras → [#139](https://github.com/deghosal-2026/agent-eval-forge/issues/139)
  - [ ] `scripts/smoke-test.sh` — end-to-end smoke test with real LLM, skipped if no API key → [#138](https://github.com/deghosal-2026/agent-eval-forge/issues/138)
  - [ ] Smoke test runs 1 scenario through each adapter (langgraph + pydantic-ai) → [#138](https://github.com/deghosal-2026/agent-eval-forge/issues/138)
  - [ ] Smoke test asserts exit code 0, valid JSON report, cost reported → [#138](https://github.com/deghosal-2026/agent-eval-forge/issues/138)
  - [ ] Cost budget for smoke test: < $0.05 per run, with budget guard → [#138](https://github.com/deghosal-2026/agent-eval-forge/issues/138)
  - [ ] `.env.example` committed, `.env` in `.gitignore` → [#139](https://github.com/deghosal-2026/agent-eval-forge/issues/139)
- [ ] **LangGraph example agent hardened** → [#136](https://github.com/deghosal-2026/agent-eval-forge/issues/136)
  - [ ] Read API key from env with clear error if missing
  - [ ] Add `--help` / argparse for standalone run
  - [ ] Test with at least 3 launch scenarios: launch-01, launch-04, launch-06
  - [ ] Verify trajectory extraction produces correct tool_call/tool_result/response steps
  - [ ] Verify cost tracking (tokens captured in artifact)
  - [ ] Verify error handling (invalid model name → clear error, not traceback)
  - [ ] Document expected environment variables
- [ ] **PydanticAI example agent hardened** → [#135](https://github.com/deghosal-2026/agent-eval-forge/issues/135)
  - [ ] Read API key from env with clear error if missing
  - [ ] Add `--help` / argparse for standalone run
  - [ ] Test with at least 3 launch scenarios: launch-01, launch-08, launch-09
  - [ ] Verify typed output extraction (structured field populated)
  - [ ] Verify trajectory extraction produces correct tool-call/tool-return/response steps
  - [ ] Verify cost tracking via `.usage()` (token counts in artifact)
  - [ ] Verify error handling (invalid model → clear error)
  - [ ] Document expected environment variables
- [ ] **Quickstart agent** → [#137](https://github.com/deghosal-2026/agent-eval-forge/issues/137)
  - [ ] `examples/quickstart_agent.py` — minimal agent (~30 lines) using PythonImportAdapter contract
  - [ ] Implements `run(payload)` that echoes plus one tool call
  - [ ] No framework dependencies (pure Python)
  - [ ] Works with `evalforge run` in README quickstart
  - [ ] Tested on clean clone (pip install, run, success)
- [ ] **Full pack mock run** → [#116](https://github.com/deghosal-2026/agent-eval-forge/issues/116)
  - [ ] `evalforge run --pack scenarios/core-launch.yaml` with python-import adapter
  - [ ] Verify all 20 scenarios report status (passed/warned/failed)
  - [ ] Verify totals: passed + warned + failed == 20
  - [ ] Verify exit code matches scenario outcomes
  - [ ] Verify JSON report is valid and complete
  - [ ] Verify markdown report renders correctly
  - [ ] Verify CI pipeline passes with full pack run
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
- LangGraph example agent runs 3+ launch scenarios end-to-end with real LLM
- PydanticAI example agent runs 3+ launch scenarios end-to-end with real LLM
- Quickstart agent works on a clean clone with no framework dependencies
- Smoke test passes in CI (skipped without API keys)
- All example agents have working `--help`, env var loading, and clear error messages


### Milestone Exit Gates
- [ ] Code review completed
- [ ] All comments added to code
- [ ] Full test suite passes (`pytest`)
- [ ] Lint clean (`ruff check` zero errors)
- [ ] Type check clean (`mypy --strict` zero errors)
- [ ] Code coverage > 90% (`pytest --cov`)

---

## M13: OSS Cleanup & Launch

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
| 5/5 | "EvalForge: A Framework-Agnostic Release Gate for AI Agents" | After M11 (launch) |

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM judge costs exceed budget during scenario development | Medium | Use mock judges during dev, real judges only in CI/integration |
| LangGraph/PydanticAI API changes break adapters | Medium | Pin framework versions, test against latest on schedule |
| Scenario packs are too brittle (depend on exact tool output) | Low | Fixtures system decouples scenarios from live tool behavior |
| v0.1 scope too broad for timeline | Medium | M4-M5 scenarios are the riskiest; can reduce to 6 launch groups if needed |
| PyPI name unavailable | Low | Verify early; fallback `agent-eval-forge` confirmed available |