# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
