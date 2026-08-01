# Agent Eval Forge — Design & Code Review Findings

This document records a comprehensive design/code/test review of the project. It classifies issues by severity, cites specific files/lines, explains why they matter, describes what “good” looks like, and provides concrete checklists to fix each item. It is intended as a living hardening plan for M8+.

## Contents

- Scope & Method
- Severity Scale
- Executive Summary
- Critical Issues
- High-Severity Issues
- Medium-Severity Issues
- Low-Severity Issues
- Optional Docker-Based Tests Plan
- Feature Gaps & Enhancements Roadmap (Beyond Defects)

---

## Scope & Method

Reviewed all docs under `docs/` (PRD, spec, WBS, design docs, adapter docs, CI guide, security review) and full source under `src/evalforge/**` (runner, scoring, adapters, models, loading, baselines, comparison, CLI, cache, security). Executed the full test suite and static checks (`ruff`, `mypy`).

Evidence:
- Tests: 283 passed locally (no skips), 1 warning
- Coverage: New code paths at 100% in engine/audit/sandbox; provider judge clients intentionally omitted from coverage (require live keys)
- Lint: `ruff` reports remaining hygiene issues (see Low Severity)
- Types: `mypy` reports 2 issues (see Low Severity)

---

## Severity Scale

- Critical: Security or correctness risks with high exploitation/impact potential; must fix before untrusted use.
- High: Material reliability/architecture gaps; should fix before broader adoption.
- Medium: Quality/robustness gaps; address in the next cycle.
- Low: Hygiene, polish, or DX clarity; opportunistic fixes or batch cleanup.

---

## Executive Summary

Strengths: Clear architecture and separation (loading → runner → adapters → scoring → CLI), strong default scoring discipline (deterministic first, judge fallback), clean Pydantic models, adapter contract documented, CI-ready CLI, new security foundations (sanitize + sandbox + audit), and good test coverage.

Key Risks: Untrusted agent execution is not consistently isolated outside the subprocess adapter; scenario trust boundaries exist as metadata but aren’t enforced; caching cost reporting is too naïve; gate/scorer misconfigs are silently skipped; judge clients remain untested in CI.

---

## Critical Issues

### C1. Untrusted Agent Execution Not Sandboxed Outside Subprocess Adapter

- Files: `src/evalforge/adapters/python_import.py` (all), HTTP adapter if present
- Type: Design & Code (Security)
- Problem: Only the subprocess adapter uses an environment-level sandbox. The python_import adapter executes arbitrary Python modules (via multiprocessing) with full filesystem and network access. HTTP agents execute remote code implicitly. No isolation boundary for these surfaces.
- Why it matters: Evaluating third-party agents can lead to RCE, filesystem exfiltration, or CI secret leakage. Sandbox must be consistent across execution surfaces.
- What Good Looks Like:
  - All adapters route agent execution through a common isolation layer honoring `SandboxConfig`.
  - Optional OS/container-level sandbox for Linux (Docker/cgroups/seccomp) with env-only fallback on macOS/Windows.
  - Clear docs of each adapter’s isolation guarantees and limitations.
- Fix Checklist:
  1. Design: Define a common “agent runner” subprocess wrapper for python_import that spawns a separate process and applies `SandboxConfig` (env stripping today; optional Docker later).
  2. Implementation: Update python_import to call the wrapper (stdin payload in, stdout envelope out), mirroring subprocess adapter semantics.
  3. HTTP adapter: Add allow/deny-list, optional proxy mediation in sandbox mode; document clearly.
  4. Tests: Add Linux-only Docker CI job to validate isolation (see Docker Plan below); add unit tests for env-stripping on all adapters.

### C2. Scenario Trust Boundaries Not Enforced (Metadata Only)

- Files: `src/evalforge/models/pack.py` (PackMetadata.trust), `src/evalforge/cli/run.py`
- Type: Design & Code (Security)
- Problem: `trust` is present (`builtin`, `local`, `external`) but it does not affect allowed adapters/tools. External packs can invoke risky surfaces.
- Why it matters: Without policy enforcement, trust metadata gives a false sense of safety.
- What Good Looks Like:
  - Policy matrix: For `external`, allow only subprocess (with `--sandbox` forced); disallow python_import; restrict HTTP endpoints; limit network/file tools.
  - Policy is evaluated in `validate` (pre-flight) and enforced in `run`.
  - Violations → strict errors in CI.
- Fix Checklist:
  1. Policy: Define trust→adapter/tool matrix in docs/spec.md.
  2. Validate: Add a trust-policy evaluator step to `evalforge validate` and surface violations.
  3. Enforce: Reject disallowed adapters/tools at runtime; log policy decisions.
  4. Persist: Include trust in run index/baseline and display in reports.

### C3. Secret Exfiltration Risk in Non-Sandboxed CI Runs

- Files: `src/evalforge/cli/run.py`, `docs/ci.md`
- Type: Design (Security, Ops)
- Problem: Outside `--sandbox`, agent processes inherit CI env (including secrets). Sanitization protects persisted artifacts/logs, not the live process.
- Why it matters: A malicious agent can read and exfiltrate CI secrets.
- What Good Looks Like:
  - CI templates default to `--sandbox`.
  - Docs clearly warn about env passthrough when sandbox is off.
- Fix Checklist:
  1. Set `--sandbox` by default in templates.
  2. Add a “Hardened CI” example in `docs/ci.md`.
  3. Warn prominently in README/spec for non-sandbox runs.

---

## High-Severity Issues

### H1. OS-Level Sandbox Missing for Linux (Env-Only Today)

- Files: `src/evalforge/security/sandbox.py`, `docs/security-review.md`
- Type: Design & Code (Security)
- Problem: Current sandbox strips env vars but does not control filesystem, network, CPU, or memory. Per-worker isolation (separate OS processes/containers per worker) is not enforced beyond the subprocess adapter and is not configurable.
- What Good Looks Like: Optional Docker/cgroups backend (`--container-runtime docker`) to run agents with minimal FS namespace, blocked outbound network, and resource caps.
- Fix Checklist:
  1. Add optional container runner path for subprocess/python_import.
  2. Document runtime requirements and fallbacks.
  3. Add Linux-only CI job to validate restrictions.

### H2. Judge Cache Cost-Savings Estimate Is Naïve

- Files: `src/evalforge/scoring/engine.py` (fixed +$0.002 per hit)
- Type: Design (Analytics)
- Problem: Reported savings ignore provider/model and tokens.
- What Good Looks Like: Provider/model-aware estimates; prefer real token usage if SDK provides it.
- Fix Checklist:
  1. Capture usage/tokens from judge SDKs where available; else use configurable defaults per model.
  2. Expose in `cache_stats` with provenance (estimated vs measured).
  3. Document logic in `docs/design/scoring.md`.

### H3. Silent Skips on Missing Gate/Scorer Hide Misconfigs

- Files: `src/evalforge/scoring/engine.py:101, 125`
- Type: Code (Reliability)
- Problem: Unknown gate/scorer triggers `continue` silently.
- What Good Looks Like: Populate a warn-level `ScoreResult` with error detail and fail under `--strict`.
- Fix Checklist:
  1. Replace silent `continue` with warn `ScoreResult`.
  2. Add strict-mode failure conversion in engine or CLI.
  3. Extend validate to catch unknown gates where feasible.

### H4. “github-actions” Output Not Written to $GITHUB_STEP_SUMMARY

- Files: `src/evalforge/cli/formatter.py`, `.github/workflows/ci.yml`
- Type: Code/Docs (UX in CI)
- Problem: Formatter returns markdown, but the workflow does not write it to the step summary file.
- What Good Looks Like: In CI mode, write returned markdown to `$GITHUB_STEP_SUMMARY`.
- Fix Checklist:
  1. In CI templates, add a step to append formatter output to `$GITHUB_STEP_SUMMARY`.
  2. In formatter or CLI, detect CI env and optionally write automatically.

### H5. Judge Clients Untested in CI (Coverage Omitted)

- Files: `src/evalforge/scoring/judge/{anthropic,ollama,openai}.py`, CI
- Type: Test Strategy
- Problem: Provider clients need API keys/services; omitted from coverage.
- What Good Looks Like: Contract tests using provider-agnostic mocks; optional live-key jobs outside the default matrix.
- Fix Checklist:
  1. Add mock-based contract tests to cover control flow.
  2. Add docs on running live provider tests with keys; keep skipped by default.

---

## Medium-Severity Issues

### M1. RunCache/SchemaCache Not Fully Wired

- Files: `src/evalforge/cache/{run_cache,schema_cache}.py`, loaders/validate paths
- Type: Design/Code (Perf)
- Problem: APIs exist; end-to-end use is limited.
- What Good Looks Like: Either wire them or prune them to avoid drift.
- Fix Checklist:
  1. Use SchemaCache in pack validation keyed by pack hash.
  2. Decide on RunCache semantics for local dev loops; else remove.

### M2. python_import + ThreadPoolExecutor Brittle on macOS (spawn)

- Files: `src/evalforge/adapters/python_import.py`, `src/evalforge/runner.py`
- Type: Design (Concurrency)
- Problem: multiprocessing “spawn” + thread pool can produce import/path issues.
- What Good Looks Like: ProcessPool or subprocess wrapper for python_import when `workers > 1`; document limitations.
- Fix Checklist:
  1. Prefer ProcessPool for python_import in parallel or wrap via subprocess runner.
  2. Add docs note for macOS spawn behavior.

### M3. Logging Strategy Missing for Library Consumers

- Files: `src/evalforge/**`
- Type: Design (DX)
- Problem: CLI relies on prints/echo; library lacks stdlib logging.
- What Good Looks Like: Module-level loggers, with CLI consuming logs for display.
- Fix Checklist:
  1. Introduce logging; keep formatter for CLI UX.
  2. Add docs for logger configuration in CI.

### M4. Baseline Rescoring vs Snapshot Comparison

- Files: `src/evalforge/cli/run.py` (compare), baselines
- Type: Design (Reproducibility)
- Problem: Candidate is compared to a rescored baseline (current engine/rubric), not a frozen metric snapshot.
- What Good Looks Like: Option to compare stored metric-results snapshots; or clearly document intended behavior.
- Fix Checklist:
  1. Add `--compare-mode {rescore,snapshot}`.
  2. Persist metric-results and prefer snapshot in strict CI.

### M5. Trust Override Not Persisted/Validated Across Artifacts

- Files: `src/evalforge/cli/run.py`, baselines
- Type: Design/Code
- Problem: `--trust` changes in-memory meta; not persisted to runs/baselines; not validated in compare.
- What Good Looks Like: Persist/display trust in run index and baseline; validate on compare.
- Fix Checklist:
  1. Persist trust in run index & baseline models.
  2. Validate consistency during compare/report.

### M6. Output JSON Schema Not Versioned

- Files: `src/evalforge/cli/run.py` (result JSON)
- Type: Design (Interop)
- Problem: No top-level schema_version; downstream parsers are brittle across versions.
- What Good Looks Like: Add `schema_version` and document contract in `docs/design/scoring.md`.
- Fix Checklist:
  1. Add schema_version to outputs.
  2. Update docs + tests.

### M7. Parallel Backpressure/Resource Knobs Sparse

- Files: `src/evalforge/runner.py`
- Type: Design (Performance)
- Problem: No queue/backpressure knobs beyond timeouts.
- What Good Looks Like: Simple backpressure controls; documented tuning recommendations.
- Fix Checklist:
  1. Add `--max-outstanding` or similar.
  2. Document CI tuning guidance.

### M8. CI/Docs Drift Risk

- Files: `docs/ci.md`, `.github/workflows/*.yml`, `.gitlab-ci.yml`
- Type: Process
- Problem: Templates and docs can get out-of-sync.
- What Good Looks Like: Note pinning, add periodic verification checklist.
- Fix Checklist:
  1. Add a “Template Verification” checklist/CI job.

### M9. Supply-Chain Hardening (SBOM, Dependency Monitoring)

- Files: `.github/workflows/ci.yml`, `.gitlab-ci.yml`, repository root (Dependabot config)
- Type: Process/Security
- Problem: No SBOM generation or automated dependency monitoring visible in CI.
- What Good Looks Like: Automated SBOM generation in CI (CycloneDX or similar) and Dependabot (or Renovate) config for Python and GitHub Actions updates; optional `pip-audit`/`safety` step.
- Fix Checklist:
  1. Add a CI step to generate SBOM (e.g., `pip install cyclonedx-bom && cyclonedx-py`), publish as artifact.
  2. Add `.github/dependabot.yml` to monitor `pip` and `github-actions` ecosystems.
  3. Optionally add `pip-audit` (or `safety`) job in CI; document how to handle CVEs (allowlist, remediation cadence).

---

## Low-Severity Issues

### L1. Ruff Hygiene Failures

- Command: `uv run ruff check .` → Found 36 errors (e.g., `W292` missing newline at EOF at `tests/test_security.py:123`), plus similar across several files.
- Type: Hygiene
- Fix Checklist:
  1. Run `ruff --fix` locally and in CI pre-commit hooks.
  2. Add `pre-commit` config if not present.

### L2. Two mypy Strict Errors

- Output:
  - `src/evalforge/security/sandbox.py:37` Missing type args for `CompletedProcess` → use `subprocess.CompletedProcess[str]`.
  - `src/evalforge/cache/judge_cache.py:31` Returning `Any` from function declared to return `dict[str, Any] | None` → narrow type or validate JSON.
- Type: Types
- Fix Checklist:
  1. Add the missing generics and adjust annotations/returns.

### L3. Deterministic Test for Judge Error Exit Path Missing

- Files: scoring engine tests
- Type: Test completeness
- Fix Checklist:
  1. Add a unit test that injects a dummy judge producing judge errors; assert exit code 3.

### L4. Scenario ID Character Set Strictness

- Files: `src/evalforge/runner.py` (`_validate_scenario_id`)
- Type: UX
- Note: Security fix added (traversal defense); consider allowing a broader safe set if needed. Document allowed set.

### L5. Formatter Centralization

- Files: `src/evalforge/cli/formatter.py`
- Type: Maintainability
- Fix Checklist:
  1. Factor common sections for consistent UX across outputs.

### L6. Large JSON Emitted to Stdout in CI

- Files: CLI/formatter
- Type: UX
- Fix Checklist:
  1. Add quiet mode for CI (suppress stdout JSON when files are written) or write to `$GITHUB_STEP_SUMMARY` instead.

---

## Optional: Docker-Based Tests Plan (Linux CI Job)

Goal: Validate isolation guarantees and reduce security risk of untrusted agents.

- Job 1: Containerized subprocess/python_import agent
  - Start a minimal Docker container, run the agent with a mounted tmpfs workdir, no outbound network (iptables), and read-only root.
  - Assert: agent cannot read parent FS/env; network calls fail; evaluation still completes.

- Job 2: Optional Ollama service smoke tests
  - Bring up an Ollama container; run `judge/ollama.py` smoke tests (flagged; skipped by default).

- Docs: Extend `docs/ci.md` with Docker-based instructions and known caveats.

---

## Feature Gaps & Enhancements Roadmap (Beyond Defects)

These are net-new capabilities and expansions that will make the product more robust and compelling.

### F1. External Benchmarks Integration (SWE-bench, WebArena)

- Scope: Enable running well-known benchmark suites so users can position their agents credibly.
- Examples: SWE-bench (code bugfix tasks), SWE-bench Verified/Lite, WebArena (autonomous web tasks), VisualWebArena (multimodal web tasks).
- What Good Looks Like:
  - Import/connectors to fetch benchmark instances into scenario packs.
  - Adapters or shims to evaluate agents against each suite’s contract.
  - Results export compatible with the benchmark’s submission format.
- Checklist:
  1. SWE-bench connector: map an instance → EvalForge scenario; supply repo checkout + patch application tool for coding agents.
  2. WebArena connector: provide browser tool adapter (Playwright) with fixture mode (static HTML snapshots) and live mode.
  3. Exporters: generate JSON/CSV in the benchmark’s expected schema.

#### Notes & References
- SWE-bench: official leaderboards and CLI tooling exist; design a “SWE-bench pack importer” that materializes specific instances (Lite/Verified) as EvalForge scenarios with: repository snapshot, failing test reference, and expected patch application check.
- WebArena-x: provides realistic autonomous web tasks; design a fixture-capture pass (record DOM/HTTP) for determinism and a live mode for end-to-end.

### F2. Browser/HTTP Tooling with Robust Fixtures

- Scope: First-class browser and HTTP tools with deterministic fixtures.
- What Good Looks Like:
  - Browser tool adapter (Playwright/Selenium) that supports:
    - `--fixtures` mode: replay from recorded DOM snapshots/har files.
    - `--live` mode: real navigation with optional sandboxed container.
  - HTTP client tool stub mapping URL→fixture file, latency injection, and error simulation.
- Checklist:
  1. Implement `BrowserAdapter` (playwright) with minimal API (goto, click, type, extract).
  2. Recording/replay utility to generate fixtures from live sessions.
  3. HTTP stub module with URL pattern matching and response variants.

#### What to Showcase
- Appeal factor: ships with a ready-to-run “web evaluation” pack (10–30 tasks) that works offline via fixtures; a one-flag switch to “go live”.
- Determinism: include a recorder to produce upgradeable fixture sets when sites change.

### F3. Security-Focused Evaluations (Prompt Injection, Exfiltration, SSRF)

- Scope: Scenarios that probe agent resilience to hostile inputs and unsafe tool use.
- What Good Looks Like:
  - Prompt-injection scenarios with explicit ground-truth of safe behavior.
  - Data exfiltration checks (agents must not print secrets/PII).
  - SSRF attempts against HTTP tools; agent must refuse.
- Checklist:
  1. Add scenario families: `prompt_injection_refusal`, `exfiltration_refusal`, `ssrf_refusal`.
  2. Deterministic scorers to validate strict refusal patterns.
  3. Strict-mode gate makes safety violations fail hard.

#### Scenario Ideas (beyond 20)
- Prompt injection variants: benign-looking HTML/MD with hidden instructions; model must ignore.
- Exfiltration bait: tool returns secrets/PII; agent must redact or refuse in output.
- SSRF variants: URLs that attempt metadata service (e.g., 169.254.169.254) — agent must refuse.

### F4. Failure Taxonomy & Analytics

- Scope: Richer analytics on failure modes to aid triage.
- What Good Looks Like:
  - Failure taxonomy: tool misuse, argument precision, safety breach, timeout, hallucination.
  - Confusion matrix per agent version; trend reports across runs.
- Checklist:
  1. Extend `ScoreResult.detail` to include normalized failure codes.
  2. Add summary sections (per-family/per-metric breakdown, confusion matrix) to markdown/GA outputs.

#### “What Good Looks Like” in Reports
- Visual deltas per scenario family (stacked bars), top failure codes, regression hot spots, cost/step histograms, and a “pass-to-fail” change log between baselines.

### F5. Hallucination & Grounding Metrics

- Scope: Retrieval-grounded checks for factuality.
- What Good Looks Like:
  - LLM-judge prompts that assess grounding against provided context.
  - Optional embedding-based similarity checks for cited vs retrieved content.
- Checklist:
  1. Add `grounding_consistency` scorer (judge + optional embeddings).
  2. Fixtures for multi-doc contexts and expected citations.

#### Scoring Hints
- Judge prompt includes explicit instruction to verify that every claim is supported by provided docs; scorer requires explicit citations (document IDs or span hashes) and penalizes unsupported claims.

### F6. Determinism & Reproducibility

- Scope: Improve reproducibility across environments.
- What Good Looks Like:
  - Record seeds, judge parameters, and serialized prompts.
  - Replay mode that re-runs the same judge prompts at `temperature=0`.
- Checklist:
  1. Persist judge prompts/params to artifacts (guarded by `--redact` if needed).
  2. Add `--replay <run_dir>` to rescore artifacts deterministically.

#### Engineering Notes
- For judge replay, persist normalized prompts with hash keys and enforce `temperature=0`; provide an environment toggle to redact prompts when handling sensitive content.

### F7. JSON Output Schema Versioning & Contracts

- Scope: Stabilize downstream consumption.
- What Good Looks Like:
  - Add top-level `schema_version` to run outputs and comparison reports.
  - Publish JSON Schema in docs and validate in CI.
- Checklist:
  1. Introduce `schema_version: v0.1` (increment on breaking changes).
  2. Provide `schemas/*.json` and validate outputs in tests.

#### Consumer Experience
- Publish a tiny `evalforge-schema` package (or JSON Schema files) so downstream tools can validate and evolve parsers without chasing breaking changes.

### F8. Plugin System & Registry (Scorers/Adapters)

- Scope: Streamlined extensibility.
- What Good Looks Like:
  - Entry-point based discovery for custom scorers/adapters.
  - `evalforge plugins list` shows third-party packages and versions.
- Checklist:
  1. Finalize entry-point group names; document template packages.
  2. Add plugin health checks (version compatibility, missing deps).

#### Ecosystem Angle
- Maintain a curated list of community scorers/adapters with quickstart snippets; add `evalforge plugins list --verbose` to show provenance and versions.

### F9. CLI DX (Config File, Scaffolding, Scenario Registry)

- Scope: Faster onboarding.
- What Good Looks Like:
  - `evalforge.toml` config (default pack, agent, output)
  - `evalforge scaffold scenario` to generate a scenario skeleton
  - Optional remote registry for scenario packs
- Checklist:
  1. Support `--config evalforge.toml` and sensible defaults.
  2. Add `scaffold` subcommand.
  3. Explore a simple Git-based pack registry spec.

#### “Beyond 20 Scenarios” Growth Plan
- Ship multiple themed packs out of the box (target: 50–100 scenarios total):
  - Retrieval & synthesis (10–15)
  - Structured extraction & schema validation (10–15)
  - Tool argument precision & avoidance (10)
  - Safety (disallowed/refusal, exfiltration, SSRF) (10–15)
  - Coding-agent mini-tasks (diff review, test failure triage) (10–15)
  - Browser/HTTP tasks (fixtures + live) (10–15)
- Make the “Launch Pack” a curated subset (20) and clearly advertise “Extended Packs” for advanced users.

### F10. Rich Reports & UI

- Scope: Human-friendly drill-down.
- What Good Looks Like:
  - Static HTML report with per-scenario detail, diffs, and traces.
  - GitHub Checks API annotations per scenario.
- Checklist:
  1. Generate HTML alongside markdown/JSON.
  2. Add optional GitHub Checks integration.

#### Appeal Boosters
- Generate a single-page static HTML report with collapsible per-scenario detail, tool traces, cost/time breakdowns, and embedded diffs. Provide a linkable online viewer style (works locally).

### F11. Observability & Telemetry

- Scope: Structured logs and metrics for large-scale runs.
- What Good Looks Like:
  - Stdlib logging with JSON handler option, per-stage timings, and tool-call events.
  - Optional OpenTelemetry export for spans/metrics.
- Checklist:
  1. Introduce module loggers; add structured logs to runner/scorer paths.
  2. Optional OTLP exporter (feature-flagged).

#### Operational Maturity
- Capture timings per stage (load → run → score → compare), record tool-call latencies and judge call counts, and expose a JSONL event stream for easy ingestion.

### F12. API/Library Surfaces

- Scope: Programmatic use by test harnesses.
- What Good Looks Like:
  - Python API to `run_pack`, `score_artifacts`, and `compare` returning dataclasses.
  - Stable contracts documented and versioned.
- Checklist:
  1. Factor CLI logic into reusable library calls.
  2. Document in `docs/spec.md` and add unit tests.

#### Integration Stories
- CI/CD bots that gate PRs using the Python API; notebooks that perform ad hoc evaluation across packs; dashboards that aggregate trends from the API artifacts.

### F13. Baseline Management UX

- Scope: Easier handling of baselines.
- What Good Looks Like:
  - Commands to diff baselines, summarize deltas, and tag runs.
  - Optional small TUI/HTML tool to browse baselines.
- Checklist:
  1. Extend `baseline` subcommands (diff, describe, tag).
  2. Add report generator for baseline deltas.

#### Expected UX
- `evalforge baseline diff v0.1.0 v0.2.0 --format markdown` prints a readable delta, with links into the HTML report when available.

### F14. Data Provenance & Versioning

- Scope: Traceability of scenario packs and fixtures.
- What Good Looks Like:
  - Record pack URI + content hash; fixture hashes; scenario semver.
  - Show provenance and version mismatches prominently.
- Checklist:
  1. Persist provenance fields in run index/baseline.
  2. Validate and warn/fail under `--strict`.

#### Provenance Fields
- Include: pack URI, pack content hash, fixture hash set, scenario semver, engine version, judge provider/model, and CLI flags. Display prominently in reports for reproducibility.

### F15. Egress Control & HTTP Policy

- Scope: Reduce network risk in live mode.
- What Good Looks Like:
  - Allowlist for domains/ports in HTTP tool; deny-by-default in external trust.
  - DNS-block in containerized runs.
- Checklist:
  1. Add HTTP policy config and enforcement hooks in HTTP adapter/tool.
  2. Document policies and provide safe defaults.

#### Safety Defaults
- Deny-by-default for external trust; explicit allowlist per pack. Provide clear error messages and a `--explain-policy` helper.

### F16. Official Docker Image & GHCR Release

- Scope: One-command onboarding.
- What Good Looks Like:
  - Publish `ghcr.io/<org>/agent-eval-forge:<version>` with all extras.
  - “Try now” recipes in docs (mount pack dir; run fixtures/live).
- Checklist:
  1. Add a publish job to CI for tagged releases.
  2. Document image usage and version pinning.

---

## Advanced Enhancements (Stretch / Differentiators)

High-impact ideas to push robustness, scale, and product appeal. Each includes a short acceptance checklist.

### X1. Scenario Authoring Toolkit & Linter
- Scope: Author reliable packs fast with guardrails.
- Checklist:
  - [ ] `evalforge lint pack.yaml` validates style, thresholds, and metric names
  - [ ] Authoring guide and templates with best practices (fixtures, budgets, safety)
  - [ ] Pack “doctor” that auto-suggests fixes (missing fields, invalid tags)

### X2. Scenario Fuzzing & Red-Teaming Generator
- Scope: Expand coverage automatically via mutations and adversarial prompts.
- Checklist:
  - [ ] Fuzzer that varies inputs/tool args within semantic bounds
  - [ ] Adversarial generator for prompt-injection and refusal scenarios
  - [ ] Corpus minimizer to keep only high-signal variants

### X3. Auto-Shrinker / Repro Minimizer for Failures
- Scope: Produce a minimal repro for failing scenarios.
- Checklist:
  - [ ] Bisection/minimization pass on input/context/tools until failure persists
  - [ ] Export minimal pack + fixtures for bug filing

### X4. Multi-Agent Orchestration Evals
- Scope: Evaluate crew/graph agents (LangGraph/CrewAI/etc.) for planning quality and handoff correctness.
- Checklist:
  - [ ] Scenario family for plan validity, task decomposition, handoff fidelity
  - [ ] Deterministic scorers for role adherence and tool ownership

### X5. Tool Approval Workflow Evals
- Scope: Probes agent adherence to approval gates (e.g., human-in-the-loop nodes).
- Checklist:
  - [ ] Scenarios that require explicit approvals; refusal on missing approval
  - [ ] Deterministic scorer for “approval requested before action”

### X6. Latency/Throughput Stress Testing
- Scope: Scale/perf characterization under load.
- Checklist:
  - [ ] Stress runner that simulates N parallel agents with variable budgets
  - [ ] Perf report (p50/p95 latency, errors, resource usage)

### X7. Budget-Aware Optimization & Acceptance Envelopes
- Scope: Quantify tradeoffs for cost/time/steps vs accuracy.
- Checklist:
  - [ ] Define acceptance envelopes (max cost/time per scenario)
  - [ ] Report Pareto suggestions (where to tighten/relax budgets)

### X8. Provider/Model Matrix Runner
- Scope: Compare multiple providers/models across the same pack.
- Checklist:
  - [ ] Matrix mode: run(pack × {model}) and aggregate deltas
  - [ ] Cost/accuracy charts and winner summaries

### X9. Prompt Template Versioning & Diffs
- Scope: Track prompt changes and their impact.
- Checklist:
  - [ ] Persist prompt templates + versions in artifacts (redactable)
  - [ ] Diffs between runs with correlation to score changes

### X10. Secrets & PII Scanning on Artifacts (Belt & Suspenders)
- Scope: Detect leakage despite sanitization.
- Checklist:
  - [ ] Integrate a configurable scanner (regex + entropy + PIIs)
  - [ ] Fail under `--strict` if sensitive content found in outputs

### X11. Compliance Hooks (SOC2-Ready)
- Scope: Help orgs meet compliance needs.
- Checklist:
  - [ ] Retention controls for audit logs, redact modes
  - [ ] Policy logs with who/what/when for scenario execution

### X12. Triage Assistant (LLM Summaries)
- Scope: Speed up human review of failures.
- Checklist:
  - [ ] Summarize top regressions, probable root causes, and suggested fixes per run

### X13. HTML Report with Deep Links & Diff Views
- Scope: Premium UX for humans.
- Checklist:
  - [ ] Collapsible per-scenario details, tool traces, cost/time charts
  - [ ] Links to baseline vs candidate diffs, filters by tags/families

### X14. Data Lake Export (Parquet/Delta)
- Scope: At-scale analytics.
- Checklist:
  - [ ] Export runs/comparisons as Parquet; schema documented
  - [ ] Example notebooks for trend analysis

### X15. Public Leaderboard Integration (Opt-In)
- Scope: “Show your work” for OSS agents.
- Checklist:
  - [ ] Exporters compatible with public leaderboards (e.g., SWE-bench)
  - [ ] One-click submission guides (if applicable)

### X16. Pack Registry & Signing (Sigstore)
- Scope: Trust the source of packs.
- Checklist:
  - [ ] Pack registry spec (URI + manifest + signatures)
  - [ ] Verify signatures at load; record provenance in artifacts

### X17. Tutorials & Notebooks Library
- Scope: Reduce time-to-value.
- Checklist:
  - [ ] Notebooks: first eval, baseline compare, matrix runs, reports
  - [ ] Clear agent integration examples for LangGraph/PydanticAI/CrewAI

### X18. Editor/IDE Integration (VSCode)
- Scope: Developer ergonomics.
- Checklist:
  - [ ] Simple VSCode extension to run `validate`/`run` and show pass/fail inline
  - [ ] Quick links to HTML/markdown reports

### X19. GitHub App PR Gate (Checks API)
- Scope: Native SCM integration.
- Checklist:
  - [ ] App that posts summaries and fails PRs on regressions/safety violations
  - [ ] Settings for packs/tags enforced per repo

### X20. Flakiness Profiler & Statistical Deltas
- Scope: Confidence in score changes.
- Checklist:
  - [ ] Rerun N times to detect flakiness; annotate flaky scenarios
  - [ ] Statistical significance for score deltas (CI bands)

### X21. A/B Gating and Canarying
- Scope: Safer adoption in prod.
- Checklist:
  - [ ] Run candidate vs baseline on sampled subsets and gate on impact
  - [ ] Roll forward/back helpers

### X22. Cost Governor
- Scope: Keep spend in control.
- Checklist:
  - [ ] Global cost cap per run; stop early if exceeded
  - [ ] Report cost per provider/model/tool

### X23. Distributed Executor (Queue/Workers)
- Scope: Scale-out.
- Checklist:
  - [ ] Pluggable executor (local, Ray, Celery) with run resumption
  - [ ] Fault-tolerant artifact writes; idempotent retries

### X24. Telemetry Export (Prometheus/Grafana)
- Scope: Ops visibility.
- Checklist:
  - [ ] Export metrics (runs, pass/fail, latencies, costs) to Prometheus
  - [ ] Example Grafana dashboards

### X25. Governance (RBAC/Policy DSL)
- Scope: Enterprise controls.
- Checklist:
  - [ ] Roles/permissions for running packs and viewing results
  - [ ] Simple policy DSL to express org rules for adapters/tools

#### Distribution
- Publish a multi-arch image (amd64/arm64) with extras preinstalled (judge/langgraph/pydanticai) and a tag for each release (e.g., `ghcr.io/<org>/evalforge:v0.1.0`). Include minimal entrypoints for `validate`/`run`.

## Notes on Already-Addressed Items

- Path traversal on `scenario_id` (Runner): Fixed via `_validate_scenario_id()` (regex `^[A-Za-z0-9_-]+$`) before file writes. Keep allowed set documented; expand safely if needed.
- Integration test stability on macOS: Parallel tests switched to subprocess adapter to avoid `spawn + threads` fragility. Documented here as M2.

---

## Close-Out Checklist (Suggested Next Sprint)

1) Security Enforcement
   - [ ] Implement trust-policy evaluator + enforcement (C2)
   - [ ] Default `--sandbox` in CI; update docs (C3)
   - [ ] Optional Docker isolation for Linux (H1)

2) Reliability & Reporting
   - [ ] Replace hardcoded judge savings with provider/model-aware logic (H2)
   - [ ] Warn/error on missing gate/scorer (H3)
   - [ ] $GITHUB_STEP_SUMMARY integration (H4)

3) Test & DX
   - [ ] Contract tests for judge clients (H5)
   - [ ] Logging API for library consumers (M3)
   - [ ] Baseline snapshot comparison option (M4)
   - [ ] Deterministic test for exit code 3 (L3)

  4) Hygiene
   - [ ] Run `ruff --fix` and add pre-commit (L1)
   - [ ] Fix `mypy` generics/returns (L2)

This document should be updated as items are addressed, with links to PRs and verification evidence.

---

## Further Hardening Ideas (Action Items)

The following are explicitly prioritized “make it super solid” items consolidated from the review. Each includes an acceptance checklist.

### A1. Enforce Trust Policies

External packs must be forced to the sandboxed subprocess adapter only; disallow `python_import`; restrict HTTP endpoints; validate at validate/run time.

- Fix Checklist:
  - [ ] Define trust→adapter/tool matrix (docs/spec.md)
  - [ ] Add a trust-policy evaluator in `validate` (fail under `--strict`)
  - [ ] Enforce policy in `run` (reject disallowed adapters/tools)
  - [ ] Provide `--explain-policy` helper to show why a combo is blocked

### A2. Optional Docker Agent Execution (Linux)

Add `--container-runtime docker` to run agents in containers with no network and least-privilege mounts; provide Linux-only CI job that validates isolation.

- Fix Checklist:
  - [ ] Define container runner interface (stdin JSON, stdout envelope)
  - [ ] Provide docker runtime path for subprocess/python_import
  - [ ] Linux CI job validates: no network, read-only root, limited mounts
  - [ ] Document operational requirements and fallbacks (macOS/Windows)

### A3. Judge Savings: Provider/Model-Aware (or Usage-Based)

Replace naïve fixed savings with provider/model-aware or usage-based estimates; expose provenance (measured vs estimated).

- Fix Checklist:
  - [ ] Capture usage/tokens from judge SDKs when possible
  - [ ] Provide per-model default cost assumptions (configurable)
  - [ ] Add provenance flag in `cache_stats` (estimated|measured)
  - [ ] Document assumptions and formulas in docs/design/scoring.md

### A4. Loud Errors for Missing Gate/Scorer

Warn/error on missing gate/scorer instead of silent continue; strict mode fails.

- Fix Checklist:
  - [ ] Emit warn-level `ScoreResult` when gate/scorer missing
  - [ ] Convert warn→fail under `--strict`
  - [ ] Extend `validate` to catch unknown gates earlier

### A5. Stdlib Logging Across Library Surfaces

Add module-level loggers and keep CLI formatter for human UX.

- Fix Checklist:
  - [ ] Introduce module loggers with structured message templates
  - [ ] Keep CLI formatter output unchanged
  - [ ] Document logger configuration in CI (docs/ci.md)

### A6. Baseline Compare Modes

Support snapshot comparison (persisted metric-results) vs rescoring; document defaults.

- Fix Checklist:
  - [ ] Add `--compare-mode {rescore,snapshot}`
  - [ ] Persist metric-results snapshot for baselines
  - [ ] Update docs and add verification tests

### A7. JSON Schema Versioning

Add schema versioning for run output and comparison reports with contract docs.

- Fix Checklist:
  - [ ] Introduce top-level `schema_version`
  - [ ] Publish JSON Schemas and validate in tests
  - [ ] Versioning policy noted in docs (semver-like)

### A8. Backpressure Knobs for Parallel Runner

Add basic knobs and CI tuning documentation.

- Fix Checklist:
  - [ ] Add `--max-outstanding` (or similar) backpressure parameter
  - [ ] Document tuning suggestions in docs/ci.md (CPU/memory/time considerations)

### A9. Supply Chain: SBOM + Dependabot/Renovate + Optional pip-audit

Strengthen supply-chain posture.

- Fix Checklist:
  - [ ] Add SBOM generation step (CycloneDX) and publish artifact
  - [ ] Add `.github/dependabot.yml` (pip + GitHub Actions)
  - [ ] Optional `pip-audit`/`safety` job; document CVE policy
  
### A10. Judge Clients: Contract Tests + Optional Live-Key Jobs

Raise confidence without forcing API keys in default CI.

- Fix Checklist:
  - [ ] Add provider-agnostic mock contract tests that cover error/success paths
  - [ ] Add optional CI jobs (manual trigger) for live-key smoke tests
  - [ ] Keep provider files documented if excluded from default coverage

---

## Execution Plan (Two Sprints)

This activity sequences the highest-impact items into two focused sprints.

### Sprint 1 — Security & Trust (A1–A2)

Goal: Make untrusted-eval story credible and repeatable.

- Scope:
  - A1: Enforce Trust Policies
    - Implement trust→adapter/tool policy, validate at `validate`/`run`
    - Persist/display trust in run index & baselines
  - A2: Optional Docker Agent Execution (Linux)
    - Add container runtime path (subprocess/python_import)
    - Linux CI job to validate network-off, restricted mounts
- Exit Criteria:
  - External packs are blocked from python_import/HTTP unless policy allows
  - Sandbox enforced for external trust
  - Docker path validated in CI (Linux)

### Sprint 2 — Reporting/Scoring + DX/Schema + Scale/Perf (A3–A8)

Goal: Improve confidence in results, developer experience, and operation under load.

- Scope:
  - A3: Judge Savings (provider/model-aware or usage-based), provenance in cache_stats
  - A4: Loud errors for missing gate/scorer; strict mode fails
  - A5: Stdlib logging: add library loggers, preserve CLI formatter UX
  - A6: Baseline compare modes: `--compare-mode {rescore,snapshot}`
  - A7: JSON schema versioning & published schemas
  - A8: Parallel backpressure knobs + CI tuning docs
- Exit Criteria:
  - Reports include more accurate cost savings with provenance
  - Misconfigurations surfaced clearly; strict mode gates as expected
  - Logging available for library consumers
  - Output contracts versioned and validated in CI
  - Parallel runs tunable with documented guidance

Optional adds (time permitting): select 1–2 “X” items (e.g., X1 linter, X10 secrets scanning, X13 HTML report) to increase appeal beyond 20 scenarios.
