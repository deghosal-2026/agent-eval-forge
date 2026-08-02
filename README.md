<div align="center">

# Agent Eval Forge

[![CI](https://github.com/deghosal-2026/agent-eval-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/deghosal-2026/agent-eval-forge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)
[![Type checked](https://img.shields.io/badge/mypy-strict-blue)](https://github.com/python/mypy)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

**Stop unsafe agent changes from shipping.**

`pytest` for agents — a framework-agnostic evaluation harness that catches
regressions before you ship: correctness, tool discipline, safety boundaries,
cost, and latency.

</div>

---

## Why

You change a prompt, swap a model, or add a new tool. The demo looks great.
Three days later, a customer hits a regression the demo never covered.

Agent teams change prompts, models, tools, and orchestration logic constantly
— but most still judge progress by eyeballing a handful of examples. That
works for demos. It fails for production. The final answer isn't the only thing
that matters: the path taken, the tools selected, the arguments passed, the
cost incurred, and the safety boundaries respected all matter.

EvalForge turns release decisions from anecdotes into evidence.

> *"Did the agent actually get better, or did it just change?"*

---

## What It Is

A **release-discipline product** for tool-using AI agents. Local-first,
CI-second. Strong default rubrics out of the box, all overridable. Built for
one job: deciding whether an agent change is safe to ship.

| Capability | Description |
|---|---|
| **Scenario packs** | YAML-defined evaluation scenarios with inputs, tools, expected behaviors, and scoring rules |
| **Trajectory scoring** | Score the agent's path — not just the final answer. Tool selection, argument quality, step efficiency |
| **Safety gating** | Catch disallowed tool use, policy violations, and data boundary breaches before they ship |
| **Regression detection** | Compare candidate versions against explicit golden baselines at scenario, family, and pack level |
| **Framework-agnostic** | Adapters for subprocess, Python import, and HTTP. Proven targets: LangGraph, PydanticAI |
| **CI-native** | Runs locally for developer decisions, in CI for enforcement. Structured exit codes for safety violations |
| **Deterministic + LLM judge** | Cheap deterministic checks first, semantic LLM-as-judge only when needed |
| **Security model** | Sandbox mode, trust policies, audit trail, API key sanitization |
| **20 launch scenarios** | Production-grade scenarios across 10 families, plus 8 security scenarios |
| **External benchmarks** | SWE-bench and WebArena connectors |

### Product philosophy

- **Safety > Correctness > Efficiency** — safety regressions fail by default
- **Explicit golden baselines** — compare against what you accepted, not what happened to run last
- **Local-first, CI-second** — catch issues before merge, enforce in CI
- **Strong default rubrics** — credible pass/fail behavior out of the box
- **Framework-agnostic by adapter** — not claimed, proven with tested integrations

---

## What It Is Not

| Not this | Why |
|---|---|
| A generic LLM eval framework | EvalForge goes deeper on scenario packs + trajectory/regression for agents |
| A hosted observability platform | EvalForge is for evaluation and regression discipline, not production tracing ownership |
| An auto-prompt optimizer | EvalForge diagnoses and measures — it does not mutate systems automatically in v0.1 |
| A benchmark leaderboard | The focus is practical agent evaluation, not infinite leaderboard collection |

---

## Quickstart

```bash
# Install
pip install agent-eval-forge

# With framework adapters and judge backends
pip install agent-eval-forge[langgraph,pydanticai,judge]

# Run a scenario pack against your agent
evalforge run \
  --pack scenarios/core-launch.yaml \
  --agent python:my_agent.py \
  --baseline v1.0.0 \
  --judge openai:gpt-4o-mini

# Save a baseline once you're happy
evalforge baseline save --name v1.0.0 --run run-20260728-001

# Gate in CI
evalforge run --pack scenarios/core-launch.yaml --agent python:my_agent.py --ci
```

See the [User Guide](docs/user-guide.md) for a complete walkthrough — first
eval in 5 minutes, all commands, and 12 real-world gotchas.

---

## Launch Pack (v0.1)

20 scenarios across 10 families, plus 8 security scenarios:

| # | Family | What it tests |
|---|---|---|
| 1 | Single-Tool Factual Retrieval | Bounded lookup with the right tool |
| 2 | Multi-Tool Retrieval Synthesis | Combining evidence from multiple sources |
| 3 | Structured JSON Extraction | Transforming messy input into valid JSON |
| 4 | Tool Argument Precision | Right tool, wrong arguments |
| 5 | Tool Avoidance | Not using tools when none are needed |
| 6 | Disallowed Tool Refusal | Respecting tool policy boundaries |
| 7 | Ambiguous Request Clarification | Asking before acting under ambiguity |
| 8 | Budget-Constrained Completion | Trading off completeness and efficiency |
| 9 | Graceful Timeout / Failure Recovery | Recovering cleanly from failing dependencies |
| 10 | Coding-Agent Regression | Diff review, test failure classification |
| + | Security Scenarios | Prompt injection, exfiltration, SSRF, sandbox escape |

All scenarios ship in `scenarios/core-launch.yaml` and `scenarios/security-launch.yaml`.

---

## Framework Adapters

| Adapter | Status | Agent spec |
|---|---|---|
| Subprocess | v0.1 | `subprocess:./agent.py` |
| Python Import | v0.1 | `python:my_pkg.agent:run` |
| HTTP | v0.1 | `http:http://localhost:8000/run` |
| LangGraph | v0.1 | `langgraph:my_pkg.graph:build_agent` |
| PydanticAI | v0.1 | `pydanticai:my_pkg.agent:build_agent` |
| CrewAI | v0.2+ | — |

---

## Scoring

Two layers, cheapest first:

1. **Deterministic scorers** (always run, free, reproducible) — tool
   correctness, argument precision, schema validity, budget adherence, safety
   gates, grounding checks. 17 scorers built-in.

2. **LLM-as-Judge scorers** (run only when configured) — output correctness,
   task completion, synthesis quality, hallucination detection, refusal
   quality. 11 judge metrics built-in. Backends: OpenAI, Anthropic, Ollama,
   MLX (Apple Silicon).

**Evaluation hierarchy:** Safety failures trump everything. Correctness
regressions warn by default. Efficiency regressions are informational.

See the [Scoring Guide](docs/scoring.md) for the full metric catalog, custom
scorers, and failure taxonomy.

---

## Security

> **⚠️ Running without `--sandbox` exposes your API keys and environment
> variables to the agent process.** Always use `--sandbox` in CI. For untrusted
> scenario packs, also use `--trust external` which restricts adapters to
> sandboxed subprocess only.

The security model includes:
- **Sandbox mode** — env stripping, filesystem isolation, optional Docker network isolation
- **Trust policies** — `trust` field on packs, adapter/tool matrix enforced at validate/run
- **Audit trail** — per-run append-only log of policy decisions
- **API key sanitization** — deep-redaction in artifacts and logs

See [Security Review](docs/security-review.md) for the full model.

---

## Field Testing

EvalForge was validated against **19 real-world open-source agents** (11
LangGraph + 8 PydanticAI) sourced from GitHub across local (MLX), cheap
(gpt-4o-mini), and better (gpt-4o) tiers. The field harness exposed integration
failures that mock-based testing completely missed — import-time side effects,
hardcoded model names, Python version skew, and nested repo structures.

| Report | Scope |
|---|---|
| [Field Test Report — 08.01.2026](docs/field-test-report-08.01.2026.md) | Roster scaled from 8 to 20 agents |
| [Field Test Report — 08.02.2026](docs/field-test-report-08.02.2026.md) | 19-agent compatibility sweep, cloud tier comparison |
| [Field Test Plan](docs/testing/field-test-plan.md) | Agent selection, sourcing, config schema, acceptance criteria |
| [Hard-Won Lessons](docs/hard-won-lessons.md) | Real-world integration and design lessons from 20+ agents |

---

## Project Status

| Milestone | Status |
|---|---|
| M0 — Scaffold | ✅ |
| M1 — Core Runner | ✅ |
| M2 — Scoring Engine | ✅ |
| M3 — Comparison & Baselines | ✅ |
| M4 — Launch Scenarios 1–5 | ✅ |
| M5 — Launch Scenarios 6–10 | ✅ |
| M6 — Framework Adapters | ✅ |
| M7 — CLI & pytest | ✅ |
| M8 — CI & Polish | ✅ |
| M9 — Hardening & Security | ✅ |
| M9.5 — Integration & Field Tests | ✅ (FT5 CI job pending) |
| M10 — Example Agents & DX | ✅ |
| M11 — Scale-Up, Docker & CI | 🔄 In progress |
| M12 — Ship v0.1.0 & Launch | ⏳ |

See the [WBS](docs/wbs.md) for the full milestone plan with GitHub issue tracking.

---

## Documentation

| Document | Description |
|---|---|
| [User Guide](docs/user-guide.md) | **Start here** — installation, first eval, all commands, gotchas |
| [PRD](docs/PRD.md) | Product requirements — the what and why, 20 canonical user journeys |
| [Spec](docs/spec.md) | Technical specification — architecture, data model, scoring, all scenarios |
| [WBS](docs/wbs.md) | Work breakdown — 13 milestones, GitHub issues linked |
| [Scenarios](docs/scenarios.md) | Scenario authoring — pack anatomy, metric reference |
| [Scoring](docs/scoring.md) | Scoring — metric categories, custom scorers, failure taxonomy |
| [CI Integration](docs/ci.md) | GitHub Actions, GitLab CI, Docker sandbox |
| [Adapters — LangGraph](docs/adapters/langgraph.md) | LangGraph adapter usage |
| [Adapters — PydanticAI](docs/adapters/pydantic-ai.md) | PydanticAI adapter usage |
| [Adapters — Custom](docs/adapters/custom.md) | How to write a custom adapter |
| [External Benchmarks](docs/adapters/benchmarks.md) | SWE-bench, WebArena connectors |
| [Security Review](docs/security-review.md) | Security model and hardening |
| [Hard-Won Lessons](docs/hard-won-lessons.md) | Real-world lessons from 20+ agents |
| [Field Test Reports](docs/field-test-report-08.02.2026.md) | Compatibility sweep across tiers |
| [CHANGELOG](CHANGELOG.md) | Release history |
| [CONTRIBUTING](CONTRIBUTING.md) | How to contribute |
| [CODE OF CONDUCT](CODE_OF_CONDUCT.md) | Community standards |
| [GOVERNANCE](GOVERNANCE.md) | Project governance |
| [SECURITY](SECURITY.md) | Security policy and reporting |

---

## Community

- [Report a bug](https://github.com/deghosal-2026/agent-eval-forge/issues/new?template=bug.md)
- [Request a feature](https://github.com/deghosal-2026/agent-eval-forge/issues/new?template=feature.md)
- [Submit a scenario pack](https://github.com/deghosal-2026/agent-eval-forge/issues/new?template=scenario.md)

---

## License

[MIT](LICENSE)
