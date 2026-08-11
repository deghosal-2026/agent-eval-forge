# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-08-10

### Added

- **Exit code enforcement (#269):** `evalforge run` and `evalforge compare` now
  exit non-zero on safety violations (code 4), judge errors (code 3), and
  regressions. `--ci` no longer suppresses exit codes.
- **Crashed-agent scoring (#270):** Scoring engine short-circuits on
  `artifact.status != "completed"`, sets aggregate score to 0.0 with
  `error_category` surfaced. Deterministic scorers no longer pass vacuously on
  empty trajectories.
- **Score-delta regression detection (#271):** Comparison engine now detects
  score drops (default threshold 0.05), not just status flips. Snapshot compare
  mode uses frozen scores without fallback rescore. `git_sha`, `agent`, `trust`,
  and `score_snapshot` populated at baseline save.
- **ToolStub wired into runner (#272):** ToolStub interception layer active in
  both python_import and subprocess adapters when `--fixtures` is set.
  `verify_consumed()` warns on unused fixtures. Deterministic hash for
  multi-entry selectors. `delay_ms` applied during stub playback.
- **Rubric criteria + trajectory in judge prompts (#273):** `expected.criteria`
  rendered into judge prompt. Trajectory summary (tool calls, step count, wall
  time, errors) sent to judges. `### Expected Answer` line omitted when
  `expected.value` is None. Deterministic gate runs unconditionally regardless
  of judge availability.
- **CLI paper cuts fixed (#274):** `python:module:function` agent spec syntax
  with `--agent-function` override. `evalforge init` scaffold passes
  `--strict` validation. `exact_match` alias removed with load-time warning.
- **Offline hybrid scorer gate (#258):** `policy_adherence` deterministic gate
  always fires regardless of judge. `judge_not_evaluated` flag set when judge
  missing. Same pattern applied to `retry_discipline`.
- **Pluggable scorer registry bridged (#250):** PluginManager scorers now
  discovered by ScoringEngine via unified registry lookup. Entry-point discovery
  wired end-to-end.
- **Run manifest (#238):** `run-manifest.json` emitted per run with OS, arch,
  Python version, dependency tree, adapter info, env var names only. Supports
  `--no-manifest` flag.
- **Execution environment labeling (#244):** `execution_environment` block in
  run JSON output. CLI summary shows OS/arch. Reuses RunManifest data.
- **Three-way outcome split (#253):** Comparison engine classifies failures as
  `adapter_failed`, `agent_crashed`, or `scenario_failed`. FailureTaxonomy
  wired into comparison. Safety violations surfaced in comparison output.
- **Adapter-agent boundary diagnostics (#241):** `trace_diff.json` emitted on
  run failure with divergence type (`stopped_early`, `skipped_step`, `hung`,
  `errored`, `silent_empty`). Subprocess and python_import diagnostics.
- **Scoring breakdown output (#242):** `scoring_breakdown` block in scenario
  result JSON with per-check pass/fail for all 17 deterministic scorers and
  11 judge metrics. Divergence classification (critical/warning).
  `--fail-on-divergence critical` CLI flag for CI gating.
- **Phantom-step scorer (#259):** Detects tool calls that don't advance state.
  Exposed in scoring breakdown. Warning when phantom ratio exceeds threshold.
- **Three-gate CI scoring (#239):** `compatibility_score`, `safety_score`,
  `quality_score` dimensions emitted separately. Per-dimension gating:
  `--fail-on compatibility|safety|quality`. GitHub Actions output updated.
- **AdapterManifest (#251):** Structured adapter metadata with SHA-256 digest
  for baseline binding. Implemented on all adapters (subprocess, python_import,
  http, langgraph, pydantic_ai, isolated, crewai, openai-agents, smolagents,
  autogen, llamaindex, claude, adk).
- **Baseline-adapter binding (#254):** Baseline bound to adapter manifest
  digest. Comparison engine detects `adapter_changed` as distinct outcome.
  Hard failure in strict mode. `--allow-adapter-change` override.
- **Model mismatch detection (#255):** Comparison engine classifies model
  changes (`gpt-4o` → `gpt-4o-mini`) as `model_changed`, distinct from
  `regressed`. Structured model info stored in baseline.
- **Model-vs-deterministic scoring comparison (#292):** Documented JPS study
  findings (62/63 result, boundary failures) in `docs/scoring-comparison.md`.
- **Adversarial scenario pack support (#293):** Documented pattern in
  `docs/scenario-authoring.md`. Example adversarial pack in
  `examples/adversarial-pack/`.
- **Two-layer defense architecture (#294):** Documented in
  `docs/architecture.md`. Layer 1 (judgment evaluator) + Layer 2 (EvalForge
  integration harness). Failure-class coverage matrix and recommended
  configuration.
- **CrewAI adapter (#277):** `crewai` adapter type with `crew.kickoff()`
  execution, trajectory extraction from task/tool history, model/provider
  redirection, manifest+digest. Extra: `pip install evalforge[crewai]`.
- **OpenAI Agents SDK adapter (#279):** `openai-agents` adapter type with
  `Runner.run_sync()`, event-stream trajectory extraction, guardrail/handoff
  traces. Extra: `pip install evalforge[openai-agents]`.
- **smolagents adapter (#281):** `smolagents` adapter type with
  `CodeAgent`/`ToolCallingAgent` execution, trajectory from agent.memory/steps.
  Extra: `pip install evalforge[smolagents]`.
- **AutoGen adapter (#283):** `autogen` adapter type with
  `AssistantAgent`/`ConversableAgent`, chat-history trajectory extraction.
  Extra: `pip install evalforge[autogen]`.
- **LlamaIndex adapter (#285):** `llamaindex` adapter type with
  `AgentRunner`/`AgentWorker`, response-source trajectory extraction.
  Extra: `pip install evalforge[llamaindex]`.
- **Claude Agent SDK adapter (#287):** `claude` adapter type with
  `claude.agents.Agent.run`, event-stream trajectory extraction.
  Extra: `pip install evalforge[claude]`.
- **Google ADK adapter (#289):** `adk` adapter type with
  `google.adk.agents.Agent`, action/event-stream trajectory extraction.
  Extra: `pip install evalforge[adk]`.
- **Field scenario packs (10 packs, 47 scenarios):** Per-adapter scenario packs
  for all 7 new framework families plus LangGraph and PydanticAI — 5 scenarios
  each (basic-tool-call, multi-step, no-tool, disallowed-tool, structured-output)
  plus a shared safety pack. SWE-bench sample pack. Located in
  `field/scenarios/`.

### Changed

- `exact_match` metric alias removed; use `output_correctness` or
  `argument_correctness` instead.
- `evalforge init` scaffold now generates `exact` type for `Expected.type`.
- `KNOWN_METRICS` augmented from plugin registry at load time.
- `--output-format github-actions` reports three-way scores.

### Fixed

- `BaselineStore.describe()` TypeError on snapshot data (sum over dicts).
- `cost_delta_usd` now correctly computed as `candidate_cost − baseline_cost`.
- `ScenarioScore` results recorded as `failed` (not `null`) when scorer raises.
- 33 known-but-unregistered metrics now emit load-time warnings instead of
  failing silently.

### Security

- v0.2.0 security review published at `docs/0.2.0/security-review.md`.

## [Unreleased]

### Added

- M1: Core runner
  - Scenario pack models (Scenario, ScenarioPack, Tool, Expected, Metric, Budget)
  - Run artifact models (RunArtifact, TrajectoryStep, Cost) with JSON round-trip
  - Error hierarchy (EvalForgeError, PackParseError, AdapterError, AgentTimeoutError)
  - YAML/JSON pack loader with validation (duplicate ids, required fields, metrics, thresholds)
  - Adapter contract + subprocess, python-import (process-isolated), and HTTP adapters
  - Invocation payload strips `expected`/`metrics` (no ground-truth leakage)
  - Runner with run_one/run_all, tag filtering, and `.evalforge/runs/<run_id>/` storage
  - `scenarios/core-launch.yaml` with all 20 launch scenarios
- M4: Launch scenarios 1-5
  - Mock launch agents (pass + fail modes) for all 10 launch-01..05 scenarios
  - Scenario tests covering pass/fail scoring, exit-code-4 disallowed tools, and fixtures
  - `ArgumentCorrectnessScorer` honors `expected.trace` tool calls (`args_match: subset`)
  - Fixture data for 8 launch tools under `scenarios/fixtures/`
- M5: Launch scenarios 6-10
  - Mock launch agents (pass + fail modes) for all 10 launch-06..10 scenarios
  - Scenario tests + FAIL_MODES coverage for scenarios 6-10
  - Engine-level end-to-end full-pack test (all 20 launch scenarios pass, exit 0)
  - Fixture data for 13 additional tools under `scenarios/fixtures/`
- M6: Framework adapters
  - LangGraph adapter (`langgraph` type) — auto-extracts trajectory from `create_react_agent` message history
  - PydanticAI adapter (`pydantic-ai` type) — auto-extracts trajectory and structured output from `Agent.run_sync()`
  - Example agents for both frameworks (`examples/`)
  - Integration tests — parametrized over launch scenarios 1-5 (skipped without optional deps)
  - Adapter documentation (`docs/adapters/`)

### Changed

- M4: Launch scenarios 1-5
  - New `ToolCalledScorer` (`tool_called` spec-catalog metric) requires every
    tool in `expected.required_tools` to be invoked; launch-02 now detects a
    missing required tool deterministically instead of relying on the judge
  - `ArgumentCorrectnessScorer` supports multi-step `expected.trace` (scores
    the fraction of declared expectations satisfied); zero required calls now
    scores 0.0 instead of passing silently
  - `core-launch-pack` bumped to 1.1.0 (scoring-criteria change, MINOR)
  - Added `data_export`/`deploy_staging` fixture data for launch-05 allowed
    tools; fixture coverage test now includes them
- M5: Launch scenarios 6-10
  - `core-launch-pack` bumped to 1.2.0 (MINOR: added fields/metrics)
  - `launch-07-step-budget` and `launch-08-partial-data-failure` now declare
    `required_tools` and are checked by the deterministic `tool_called` scorer
  - Fixture coverage test renamed to `test_fixture_data_covers_launch_tools`

### Fixed

- Malformed agent envelopes (invalid status, non-dict output) normalize to `error` artifacts
  instead of aborting the run
- Run index sanitizes agent config (no secrets) and records selected tag filter + timestamps
- Reusing a run id now raises instead of silently overwriting artifacts
- Python-import adapter no longer hangs if the worker process dies abnormally
- Non-numeric metric thresholds raise a clear `PackParseError` instead of `TypeError`


- M0: Project scaffold
  - Python package structure under `src/evalforge/` (models, adapters, scoring, baselines, comparison, cli)
  - `pyproject.toml` with dependencies, dev extras, and `evalforge` console entry point
  - `uv` for dependency management
  - ruff linting, mypy strict mode, pytest with shared fixtures
  - GitHub Actions CI pipeline (lint, typecheck, test, coverage)
  - Dependabot for dependency updates
  - `.env.example`, `CONTRIBUTING.md`, `CHANGELOG.md`
