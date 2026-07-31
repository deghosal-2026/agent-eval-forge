# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- M0: Project scaffold
  - Python package structure under `src/evalforge/` (models, adapters, scoring, baselines, comparison, cli)
  - `pyproject.toml` with dependencies, dev extras, and `evalforge` console entry point
  - `uv` for dependency management
  - ruff linting, mypy strict mode, pytest with shared fixtures
  - GitHub Actions CI pipeline (lint, typecheck, test, coverage)
  - Dependabot for dependency updates
  - `.env.example`, `CONTRIBUTING.md`, `CHANGELOG.md`
