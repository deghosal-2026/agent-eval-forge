# agent-eval-forge

**Stop unsafe agent changes from shipping.**

A framework-agnostic evaluation harness for tool-using AI agents. Define scenario packs, run agents consistently, score outcomes and trajectories, and gate releases with evidence — not vibes.

## What It Does

| Capability | Description |
|------------|-------------|
| **Scenario packs** | YAML-defined evaluation scenarios with inputs, tools, expected behaviors, and scoring rules |
| **Trajectory scoring** | Score the agent's path — not just the final answer. Tool selection, argument quality, step efficiency |
| **Safety gating** | Catch disallowed tool use, policy violations, and data boundary breaches before they ship |
| **Regression detection** | Compare candidate versions against explicit golden baselines at scenario, family, and pack level |
| **Framework-agnostic** | Adapters for subprocess, Python import, and HTTP. Proven targets: LangGraph, PydanticAI |
| **CI-native** | Runs locally for developer decisions, in CI for enforcement. Exit codes for safety violations |
| **Deterministic + LLM judge** | Cheap deterministic checks first, semantic LLM-as-judge only when needed |

## Quickstart (Coming in v0.1)

```bash
# Install
pip install agent-eval-forge

# Run a scenario pack against your agent
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent python:my_agent.py \
  --baseline v1.0.0 \
  --judge openai:gpt-4o-mini

# Save a baseline after you're happy
evalforge baseline save --name v1.0.0 --run .evalforge/runs/run-20260728-001.json

# Compare future versions
evalforge compare --candidate .evalforge/runs/run-latest.json --baseline v1.0.0

# Gate in CI
evalforge run --pack scenarios/core-launch.yaml --agent python:my_agent.py --ci
```

## Product Philosophy

EvalForge is a **release-discipline product** first. The primary job is deciding whether an agent change is safe to ship.

- **Safety > Correctness > Efficiency** — safety regressions fail by default
- **Explicit golden baselines** — compare against what you accepted, not what happened to run last
- **Local-first, CI-second** — catch issues before merge, enforce in CI
- **Strong default rubrics** — credible pass/fail behavior out of the box
- **Framework-agnostic by adapter** — not claimed, proven with tested integrations

> **⚠️ Security Warning**: Running without `--sandbox` exposes your API keys and environment variables to the agent process. Always use `--sandbox` in CI. For untrusted scenario packs, also use `--trust external` which restricts adapters to sandboxed subprocess only.

## What It Is Not

- Not a generic LLM eval framework
- Not a hosted observability platform
- Not an auto-prompt optimizer
- Not a benchmark leaderboard or vanity product

## Documentation

| Doc | Description |
|-----|-------------|
| [PRD](docs/PRD.md) | Product requirements — what and why |
| [Spec](docs/spec.md) | Technical specification — architecture, data model, scoring, all 20 CUJs |
| [WBS](docs/wbs.md) | Work breakdown — 12 milestones, 118 tasks, GitHub issues linked |

## Launch Pack (v0.1)

20 individual scenarios across 10 scenario families:

1. Single-Tool Factual Retrieval
2. Multi-Tool Retrieval Synthesis
3. Structured JSON Extraction
4. Tool Argument Precision
5. Tool Avoidance When Not Needed
6. Disallowed Tool Refusal
7. Ambiguous User Request Clarification
8. Budget-Constrained Completion
9. Graceful Timeout / Failure Recovery
10. Coding-Agent Regression (diff review, test classification)

## Framework Adapters

| Adapter | Status |
|---------|--------|
| Subprocess (CLI agents) | v0.1 |
| Python Import (native agents) | v0.1 |
| HTTP (local server agents) | v0.1 |
| LangGraph | v0.1 |
| PydanticAI | v0.1 |
| CrewAI | v0.2+ |

## Project Status

- [x] PRD approved
- [x] Spec approved
- [x] WBS created (118 tasks across 12 milestones)
- [x] M0: Scaffold
- [ ] M1-M11: Build through launch
- [ ] v0.1 release

See [WBS](docs/wbs.md) for the full milestone plan with GitHub issue tracking.

## License

MIT
