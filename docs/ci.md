# CI Integration Guide

## Overview of CI Modes

EvalForge provides first-class support for continuous integration pipelines.
When running under CI, use the `--ci` flag to:

- **Structured exit codes**: Exit 0 on all pass, exit 1 on any failure (regression, crash, or threshold miss). Non-CI runs always exit 0.
- **Structured JSON output**: Use `--output-format json` to produce machine-parseable results.
- **GitHub Actions annotations**: Use `--output-format github-actions` to emit workflow commands that annotate PRs with check annotations directly on the source file.
- **Suppress interactive features**: The `--ci` flag disables progress spinners, color output, and other TTY-only features.

## Pre-flight Validation

Before running a full evaluation, validate your configuration with the
`validate` command. This catches schema errors, missing files, and
misconfigured agents early:

```bash
evalforge validate --pack scenarios/core-launch.yaml --strict
```

Add `--pre-flight` to also verify that the agent can be instantiated without
actually running the evaluation:

```bash
evalforge validate --pre-flight --agent python:my_agent.py --strict
```

The `--strict` flag turns warnings into errors, which is recommended for CI.

Exit codes:

- **0**: Validation passed
- **1**: Validation failed (schema errors, missing files, etc.)

## Full Evaluation Runs

Run the full evaluation pack in CI:

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent python:my_agent.py \
  --output .evalforge \
  --output-format github-actions \
  --ci
```

### Fixtures Mode

For smoke-testing the evaluation framework itself (without a real agent), use
`--fixtures` to run with built-in mock agents:

```bash
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent python:fixtures.echo_agent \
  --output .evalforge \
  --output-format github-actions \
  --ci \
  --fixtures
```

## Baseline Comparison in CI

To detect regressions, compare results against a saved baseline:

```bash
# Generate baseline (run once, commit the results)
evalforge run --pack scenarios/core-launch.yaml --agent python:v1.0 --output baselines/

# In CI, compare current run against baseline
evalforge compare --current .evalforge/runs/ --baseline baselines/ --format github-actions
```

The `compare` command exits non-zero when scores drop below the configured
threshold, which fails the CI step. Thresholds are defined per-scenario in
the pack YAML under `thresholds.min_score`.

## GitHub Actions Example

A complete workflow template is available at
`.github/workflows/ci-evalforge.yml`. Key points:

- Use `astral-sh/setup-uv` for fast, cached dependency installation
- Always upload artifacts with `if: always()` so results are available even
  on failure
- Set `checks: write` in `permissions` to enable PR annotations
- Run `validate` before `run` to fail fast on configuration errors

### Docker-Based Sandbox Test (Linux)

The CI includes a `docker-sandbox` job that builds the project Docker image and executes an evaluation inside a container with `--network none`. This validates that evaluations complete without network access (environment-only isolation check):

```bash
docker build -t evalforge-sandbox -f Dockerfile .
docker run --rm --network none evalforge-sandbox \
  bash -lc "uv run evalforge run \
    --pack scenarios/core-launch.yaml \
    --agent subprocess:'python tests/fixtures/echo_agent.py' \
    --output .evalforge \
    --output-format json \
    --ci \
    --fixtures"
```

Notes:
- This validates no-network behavior. For full OS-level sandbox (FS/network/cgroups), consider a dedicated container runtime flow (Docker/cgroups) with explicit mount/network policies. See the Security Review for recommendations.

## GitLab CI Notes

Adapt the GitHub Actions template for GitLab CI:

```yaml
stages:
  - validate
  - eval

variables:
  UV_CACHE_DIR: .uv-cache

cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - $UV_CACHE_DIR

validate:
  stage: validate
  image: python:3.11-slim
  before_script:
    - pip install uv && uv sync --extra dev
  script:
    - uv run evalforge validate --pack scenarios/core-launch.yaml --strict
    - uv run evalforge validate --pre-flight --agent python:my_agent.py --strict

eval:
  stage: eval
  image: python:3.11-slim
  before_script:
    - pip install uv && uv sync --extra dev
  script:
    - uv run evalforge run --pack scenarios/core-launch.yaml
      --agent python:my_agent.py --output .evalforge --output-format json --ci
  artifacts:
    paths:
      - .evalforge/runs/
    when: always
```

## Common Configuration Advice

- **Pin Python version**: Always pin `python-version` to avoid unexpected
  breakage from new Python releases.
- **Cache uv packages**: Use `enable-cache: true` with `setup-uv` to speed up
  installs by 10-20x on subsequent runs.
- **Fail fast**: Run `validate --strict` before `run` to catch configuration
  errors immediately.
- **Artifact retention**: Set a short retention period (e.g. 7 days) for
  evaluation artifacts to avoid storage bloat.
- **Secrets**: If your agent needs API keys, pass them as CI secrets via
  environment variables. EvalForge passes environment through to the agent
  process.
- **Sandbox**: Prefer `--sandbox` in CI to strip environment variables from agent processes. Hardened CI can also run agents inside Docker with `--network none` (see Docker-Based Sandbox Test).
- **Parallel runs**: For large packs, consider splitting scenarios across
  multiple CI jobs using a matrix strategy with `--filter scenario_name`.

## Public Agent Evaluation Recipes (LangGraph & PydanticAI)

You can evaluate public example agents for LangGraph and PydanticAI. Two approaches:

1) Use the included fixtures (recommended for CI stability):
   - `tests/fixtures/langgraph_agent.py`
   - `tests/fixtures/pydantic_ai_agent.py`
   These are minimal agents wired for deterministic runs. Run adapter integration tests by installing extras:
   ```bash
   uv sync --extra langgraph --extra pydanticai
   uv run pytest tests/test_adapters_integration.py -q
   ```

2) Evaluate public examples from docs/repos (best-effort; may be flaky if upstreams change):
   - LangGraph: clone a minimal graph agent from the official examples and expose a `run(payload)` entrypoint. Then:
     ```bash
     evalforge run --pack scenarios/core-launch.yaml --agent python:my_langgraph_example.run --ci --fixtures
     ```
   - PydanticAI: similar flow — ensure an importable module with `run(payload)` exists.

Tips:
- Prefer vendoring a minimal example in your repo for stability.
- For live external calls, switch from `--fixtures` to `--live` (mutually exclusive) so agents call real tools.
- For untrusted third-party examples, force `--sandbox` and/or Docker execution in CI.
