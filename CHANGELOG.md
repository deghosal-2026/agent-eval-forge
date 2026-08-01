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
