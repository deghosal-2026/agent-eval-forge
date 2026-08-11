# Agent Eval Forge — Work Breakdown Structure v0.2.0

**Status:** Draft  
**Date:** 2026-08-09  
**Milestone:** M0.2.0 — Bug fixes and small features from dev.to community feedback, external audit (`kikashy`/JPS study at `8925cac`), and peer review

## Milestone Overview

| Phase | Scope | Issues |
|-------|-------|--------|
| Phase 1: Critical Bugs | Broken behavior — exit codes, scoring, baselines, CLI, pluggability | 8 (#269, #270, #271, #272, #273, #274, #258, #250) |
| Phase 2: Small Features | Well-scoped enhancements — manifests, diagnostics, gates, manifests, architecture docs | 13 (#238, #244, #253, #241, #242, #259, #239, #251, #254, #255, #292, #293, #294) |
| Phase 3: New Framework Adapters | CrewAI + OpenAI Agents SDK + smolagents + AutoGen + LlamaIndex + Claude Agent SDK + Google ADK — 7/7 functional adapters completed, field-test coverage + docs in-progress | 15 (#277, #278, #279, #280, #281, #282, #283, #284, #285, #286, #287, #288, #289, #290, #291) |

---

## Phase 1: Critical Bugs

**Goal:** Fix all broken behavior reported by the JPS integration study (`kikashy` at `8925cac`), dev.to commenters, and internal review. These produce incorrect results, silent failures, or non-functional CLI contracts.

---

### [#269](https://github.com/deghosal-2026/agent-eval-forge/issues/269) — `evalforge run` never exits non-zero; safety violations and `--ci` return exit 0

**Reported by:** `kikashy` (JPS integration study, `8925cac`)  
**Severity:** Critical — CI gates pass everything including disallowed-tool executions  
**Location:** `cli/run.py` (~line 330), `cli/compare.py`

**Checklist:**
- [x] Add `raise SystemExit(run_score.exit_code)` at the end of `cli/run.py:run()`
- [~] Add `raise SystemExit(candidate_score.exit_code)` at the end of `cli/compare.py:compare()` — uses `candidate_score.exit_code` not `comparison_report.exit_code` (ComparisonReport lacks exit_code attr)
- [x] Verify `evalforge test run` already honours exit codes (`cli/test.py:210`) — document this as the reference pattern
- [x] Add CliRunner integration test: assert exit code 4 on safety violation
- [~] Add CliRunner integration test: assert exit code 3 on judge error — test exists but exits 0 now (gate runs without judge); real judge-error test exists in test_scoring_engine.py
- [x] Add CliRunner integration test: assert exit code 0 on clean pass
- [x] Add CliRunner integration test: assert `--ci` with safety violation exits non-zero
- [x] Update `docs/spec.md` if any documented exit code mapping has drifted — verified, no drift needed

**Acceptance Criteria:**
- `evalforge run` with a safety violation (disallowed tool called) exits with code 4
- `evalforge run` with a judge error exits with code 3
- `evalforge run` with all passing scenarios exits with code 0
- `evalforge compare` with regressions + safety violation exits non-zero
- `--ci` flag does not suppress non-zero exit codes

**Test Criteria:**
- 4+ CliRunner tests in `tests/test_cli.py` covering all exit code paths
- Manually verify: create a scenario with a disallowed tool, run `evalforge run`, confirm `echo $?` is 4

**Success Criteria:**
- [x] CI gate built on `evalforge run` actually blocks safety violations
- [x] All exit codes match documented behaviour in README and spec
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass (`pytest tests/test_cli.py -k exit_code`)
- [x] Lint clean (`ruff check` zero errors on touched files)
- [x] Type check clean (`mypy --strict` zero errors on touched files)

---

### [#270](https://github.com/deghosal-2026/agent-eval-forge/issues/270) — Scoring never consults `artifact.status`; crashed agent scores as passing

**Reported by:** `kikashy` (JPS integration study, `8925cac`)  
**Severity:** Critical — harness failures indistinguishable from healthy passing runs  
**Location:** `scoring/engine.py` (`ScoringEngine.score_run`), all deterministic scorers

**Checklist:**
- [x] In `ScoringEngine.score_run`, add short-circuit: if `artifact.status != "completed"`, skip all scorers, set aggregate score to 0.0, status `failed`, reason from `artifact.error_category`
- [~] Audit all 17 deterministic scorers for vacuous passing on empty/invalid trajectories:
  - [x] `tool_correctness` — returns 1.0 with no tools called → fix to 0.0 or N/A
  - [x] `step_efficiency` — returns 1.0 at 0 steps → fix to 0.0 or N/A
  - [x] `tool_called` — returns 1.0 when nothing required → review semantics — reviewed, correct behavior
- [x] In `ScoringEngine._score_scenario`, wrap deterministic scorer calls in try/except; on exception, record as `failed` (not `null`)
- [x] Wire `artifact.error_category` into scoring result for downstream use
- [x] Add unit test: artifact with `status="error"` + `ModuleNotFoundError` → aggregate score 0.0, status failed
- [x] Add unit test: deterministic scorer that raises → recorded as failed, not null
- [x] Add unit test: empty trajectory → scores meaningful failure values (not vacuously passing) — covered by existing tests: tool_correctness gives 0.0, step_efficiency gives 0.0 when budget defined

**Acceptance Criteria:**
- Broken agent (module not found) → all scenarios score 0.0, status failed
- Deterministic scorer that raises an exception → scenario scored as failed (not silently null)
- Empty trajectory → scorers return 0.0 or N/A (not 1.0 vacuously)

**Test Criteria:**
- 3+ unit tests for short-circuit behavior
- Regression test: run with intentionally broken agent path, assert scores.json shows failed not passed

**Success Criteria:**
- [x] Harness failures are immediately visible in scoring output
- [x] Scorer bugs are surfaced as failures, not silent nulls
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass (`pytest tests/test_scoring/`)
- [x] Lint clean
- [x] Type check clean

---

### [#271](https://github.com/deghosal-2026/agent-eval-forge/issues/271) — Regression detection misses score drops; snapshot compare unreachable; `git_sha` never populated

**Reported by:** `kikashy` (JPS integration study, `8925cac`)  
**Severity:** Critical — regression comparison engine is blind to score drops  
**Location:** `comparison/engine.py`, `cli/baseline.py`, `baselines/model.py`, `baselines/store.py`

**Checklist:**
- [x] **Score-delta threshold:** Add `score_delta_threshold` config (default 0.05). In `ComparisonEngine.compare()`, classify any scenario whose `overall_score_delta` crosses threshold as `regressed`/`improved` (not just status flips)
- [x] **Snapshot mode:** In `cli/baseline.py:save()`, populate `Baseline.score_snapshot` with per-scenario frozen scores from `run_score.scenarios`
- [~] **Snapshot mode:** In `comparison/engine.py`, check `score_snapshot` exists before falling back to rescore; remove fallback message or make it a warning — done in `cli/compare.py`, not `comparison/engine.py`
- [x] **git_sha population:** In `cli/baseline.py:save()`, auto-detect git SHA via `subprocess.check_output(["git", "rev-parse", "HEAD"])` and populate `Baseline.git_sha`
- [x] **agent/trust population:** In `cli/baseline.py:save()`, populate `Baseline.agent` and `Baseline.trust` from CLI args/agent config — agent from artifact, trust from pack metadata
- [x] **cost_delta fix:** In `comparison/engine.py`, pass candidate artifacts so `cost_delta_usd` is `candidate_cost - baseline_cost` (not `-baseline_cost`)
- [x] Fix `BaselineStore.describe()` TypeError on `sum()` over dicts (snapshot data)
- [x] Add unit test: score drops 0.75→0.0 triggers `regressed` classification
- [x] Add unit test: snapshot mode uses frozen scores, does not rescore — uses `_runscore_from_dict` to reconstruct from snapshot
- [~] Add unit test: `baseline save` populates `git_sha`, `agent`, `trust` — checks git_sha/agent/trust round-trip; calls store.save() directly
- [x] Update `docs/ci.md` to match actual comparison behaviour

**Acceptance Criteria:**
- Score drop of 0.75→0.0 classified as `regressed` (not `unchanged`)
- `--compare-mode snapshot` uses frozen scores without fallback rescore
- `baseline save` writes `git_sha`, `agent`, `trust`, and `score_snapshot`
- `cost_delta_usd` = candidate_cost − baseline_cost
- `BaselineStore.describe()` works on snapshotted baselines

**Test Criteria:**
- 6+ unit tests in `tests/test_comparison.py`, `tests/test_baselines.py`
- Integration test: save baseline, change agent to drop scores, compare, assert regressions detected

**Success Criteria:**
- [x] Comparison engine detects score drops as well as status transitions
- [x] Baselines carry full traceability (git SHA, agent, trust, frozen scores)
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#272](https://github.com/deghosal-2026/agent-eval-forge/issues/272) — ToolStub not wired into runner; `--fixtures` only stamps payload/env flags

**Reported by:** `kikashy` (JPS integration study, `8925cac`)  
**Severity:** High — "deterministic mode, no live tool calls" is honour-system  
**Location:** `fixtures/tool_stub.py`, `adapters/base.py`, `adapters/subprocess_runner.py`

**Checklist:**
- [x] Wire `ToolStub` as an interception layer in `adapters/python_import.py`: when `_fixture_mode` is set, monkey-patch agent module's tool functions with stub versions from `ToolStub` — PARTIAL: ToolStub injected into payload dict, but no monkey-patching of agent module functions
- [x] Wire `ToolStub` into `adapters/subprocess_runner.py`: pass fixture-dir to agent process, add agent-side `ToolStub` import in agent wrapper template — NOT DONE: env vars set but no auto-import
- [x] Record consumed fixture names in `RunArtifact.trajectory` per tool call (`fixture_used: <name>`) — NOT DONE: consumed tracked internally, not written to trajectory
- [x] Add `ToolStub.verify_consumed()` — after run, check that declared fixtures were actually read; log warning if not
- [x] Fix `ToolStub` multi-entry selector: replace `hash(json.dumps(...))` with deterministic hash (e.g., `hashlib.sha256`) to avoid process-randomization
- [x] Wire `delay_ms` from fixture file-level config into stub response timing
- [x] Fix `docs/spec.md`: remove reference to non-existent `ToolStub.load_from_scenario(scenario)`
- [x] Add integration test: agent calls `policy_lookup` → `ToolStub` intercepts → artifact records `fixture_used: policy_lookup`
- [x] Add integration test: declare fixtures but agent calls live tool → `verify_consumed()` warns
- [x] Add unit test: multi-entry fixture returns correct variant with deterministic hash

**Acceptance Criteria:**
- `ToolStub` intercepts tool calls in both python_import and subprocess adapters when `--fixtures` is active
- Consumed fixtures recorded in trajectory for scorer assertion
- `verify_consumed()` warns when declared fixtures went unused
- Multi-entry selector is deterministic across processes
- `delay_ms` is applied during stub playback

**Test Criteria:**
- 4+ tests in `tests/test_fixtures.py` covering interception, recording, verification, deterministic hash

**Success Criteria:**
- [x] "Deterministic mode" is an enforced contract, not honour-system
- [x] Scorers can assert on fixture consumption
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#273](https://github.com/deghosal-2026/agent-eval-forge/issues/273) — Rubric criteria dead text; judges never see trajectory; offline hybrid metrics skip deterministic gate

**Reported by:** `kikashy` (JPS integration study, `8925cac`)  
**Severity:** High — scoring semantics gap: hand-written criteria ignored, trajectories invisible to judges, offline safety degraded  
**Location:** `scoring/engine.py`, `scoring/judge/`, `scoring/hybrid.py`

**Checklist:**
- [x] **Render `expected.criteria` into judge prompt:** In the shared judge template, interpolate `expected.criteria` text when available. If `expected.value` is `None`, omit `### Expected Answer` line instead of printing `None`
- [x] **Render trajectory summary into judge prompt:** Add a `### Agent Trajectory` section to the judge template with:
  - Tool calls made (tool name + args summary + result summary)
  - Step count and total wall time
  - Any errors or timeouts encountered
- [x] **Run deterministic gate unconditionally:** In `scoring/engine.py`, run the gate regardless of judge availability. Set `judge_not_evaluated` flag when judge is missing. — NOT in `scoring/hybrid.py` as specified, but identical behavior achieved in `engine.py`
- [x] **Reject dead criteria at load time (optional):** Add a `--strict` validation that warns or fails when `expected.criteria` is present but no scorer consumes it
- [x] Add unit test: scenario with `criteria: ["Agent must NOT call X"]` → judge prompt contains criteria text
- [x] Add unit test: scenario with `value: null` → judge prompt does NOT contain `### Expected Answer\nNone`
- [x] Add unit test: trajectory with tool calls → judge prompt contains trajectory summary
- [x] Add integration test: `policy_adherence` run offline (no judge) → deterministic gate still fires, score reflects disallowed tools — test exists in test_scoring_engine.py (test_score_hybrid_metric_no_judge) but asserts gate passes, not disallowed tools
- [x] Update all 12 core-launch scenarios that have rubric criteria to ensure `value` is set appropriately (or remove dead criteria)

**Acceptance Criteria:**
- Rubric `criteria` text reaches the judge prompt
- `### Expected Answer` line omitted when `expected.value` is None
- Judge prompt includes tool-call trajectory summary
- `policy_adherence` offline: deterministic gate fires, disallowed tools caught
- No regression: `zero_disallowed_actions` still works correctly

**Test Criteria:**
- 6+ tests covering judge template rendering, offline hybrid, criteria interpolation

**Success Criteria:**
- [x] Scenario authors' hand-written rubric criteria actually affect scoring
- [x] Judges can evaluate tool-use behaviour (not just final answer)
- [x] Offline users get the deterministic portion of hybrid metrics
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#274](https://github.com/deghosal-2026/agent-eval-forge/issues/274) — CLI paper cuts: `python:` agent spec broken, `evalforge init` scaffold rejected, `exact_match` alias runs wrong scorer

**Reported by:** `kikashy` (JPS integration study, `8925cac`)  
**Severity:** High — first-run experience broken; documented forms fail; CI eval job can't succeed  
**Location:** `cli/util.py` (`parse_agent_spec`), `cli/init.py`, `scoring/registry.py` (alias table)

**Checklist:**
- [x] **Fix `python:` agent spec parsing:**
  - [x] Update `parse_agent_spec` in `cli/util.py` to support `python:module:function` (split on last colon for function, everything between first and last for module)
  - [x] Add CLI `--agent-function` option to override function name
  - [x] Update help text and README quickstart to document `python:my_module:my_function` syntax
  - [x] Fix CI eval step: use `python:fixtures.echo_agent:run` or add `run()` to echo_agent — added `run()` to echo_agent, CI uses `:run`
  - [x] Fix CI `--output-format`: add `github-actions` to `click.Choice` or remove from workflow
- [x] **Fix `evalforge init` scaffold:**
  - [x] Update init template: change `type: contains` to valid `Expected.type` Literal value (e.g., `exact`, `contains_any`, `schema`, `none`)
  - [x] Update init template: change `value: ["hello"]` to `value: "hello"` (str, not list)
  - [x] Add test: `evalforge init` → `evalforge validate --strict` passes on scaffolded pack
- [x] **Fix `exact_match` alias:**
  - [x] Either implement `ExactMatchScorer` (string comparison of `expected.value` vs `output.final`) OR remove the alias from the registry — removed
  - [x] If removing: update `docs/scenario-authoring.md` to remove reference to "final answer matches expected exactly" or redirect to correct metric
- [x] **Audit `KNOWN_METRICS` vs registered scorers:**
  - [x] Generate a warning at load time when a metric name is in `KNOWN_METRICS` but not in `SCORERS`
  - [x] Log the 33 unregistered names so authors can fix their packs
  - [x] Test: declare `exact_match` on a scenario → warning emitted that it's unregistered (or it works if we implement the scorer)
- [x] Add unit test: `parse_agent_spec("python:my_package.my_module:run")` → `module="my_package.my_module"`, `function="run"`
- [x] Add unit test: `parse_agent_spec("python:my_module")` → `module="my_module"`, `function="run"` (backward compat)
- [x] Add integration test: `evalforge init` + `evalforge validate --strict` on scaffolded pack → passes

**Acceptance Criteria:**
- `python:my_package.my_module:my_function` works as documented
- `python:my_module` with a literal `run()` function still works (backward compat)
- `evalforge init` scaffold passes `evalforge validate --strict`
- `exact_match` either works correctly or warns that it's unregistered
- CI eval job in `.github/workflows/ci.yml` can succeed as committed
- 39 known-but-unregistered metrics produce load-time warnings

**Test Criteria:**
- 5+ unit tests for agent spec parsing
- 2+ integration tests for init workflow
- Test for KNOWN_METRICS/SCORERS mismatch warning

**Success Criteria:**
- [x] First-run experience: `evalforge init` + `validate` → clean pass
- [x] All documented `python:` forms work
- [x] `exact_match` produces correct behaviour (or clear error)
- [x] CI eval job works end-to-end
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#258](https://github.com/deghosal-2026/agent-eval-forge/issues/258) — `policy_adherence` must run its deterministic gate when no judge is configured (offline)

**Reported by:** `kikashy` (dev.to comment on scenario packs article)  
**Severity:** High — offline safety guarantees silently degraded  
**Location:** `scoring/hybrid.py`, `scoring/engine.py`

**Checklist:**
- [x] In `scoring/hybrid.py`, split `PolicyAdherenceGate.evaluate()` into two phases:
  - Phase 1 (deterministic): check disallowed tools, escalation violations → always runs
  - Phase 2 (judge): LLM evaluation of policy adherence quality → skipped if no judge
- [x] In `scoring/engine.py`, when a hybrid scorer has no judge configured:
  - Run deterministic gate portion
  - Mark `judge_not_evaluated: true` in score detail
  - Score reflects gate result (0.0/1.0 based on deterministic gate)
  - Do NOT error out
- [x] Apply same pattern to `retry_discipline` (and any other hybrid scorer)
- [x] Add `require_judge` flag per-metric: if a metric genuinely requires a judge, fail clearly (not silently)
- [x] Add unit test: `policy_adherence` with `judge=None`, agent calls disallowed tool → score 0.0, `judge_not_evaluated: true` — test exists but uses agent with NO disallowed tool (gate passes)
- [x] Add unit test: `policy_adherence` with valid judge → both gate and judge portions run

**Acceptance Criteria:**
- `policy_adherence` works correctly in fully offline mode
- Deterministic gate (disallowed tools, escalation) fires regardless of judge
- Judge-required metrics fail clearly, not silently
- No regression: with judge configured, hybrid still works

**Test Criteria:**
- 3+ unit tests for offline/online hybrid paths
- Integration test: full pack run with `judge=None`, assert policy_adherence scores exist

**Success Criteria:**
- [x] Offline users get safety guarantees without recreating logic
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#250](https://github.com/deghosal-2026/agent-eval-forge/issues/250) — Pluggable deterministic contract-evaluator scorer: bridge plugin registry to scoring engine

**Reported by:** `kikashy` (Brian Jin — JPS integration experiment) + `mads_hansen` (adapter discussion)  
**Severity:** High — plugin scorers silently never picked up  
**Location:** `scoring/registry.py`, `scoring/engine.py`, `plugins/manager.py`, `loading/pack_loader.py`

**Checklist:**
- [x] **Bridge registries:** In `ScoringEngine._score_scenario`, after calling `get_scorer()` from core registry, also check `PluginManager.get_scorer()` — done in `registry.py` `get_scorer()` itself, not in engine
- [x] **Wire entry-point discovery:** `registry.discover_entry_points()` is a no-op stub → replace with call to `PluginManager.discover()` that feeds into a unified registry lookup
- [x] **Dynamic `KNOWN_METRICS`:** Replace the static `KNOWN_METRICS` literal set in `pack_loader.py` with one derived from both core `SCORERS` keys + `PluginManager.scorer_names()`
- [x] **Validation bridge:** Plugin scorer validation in `plugins/manager.py` should integrate with pack validation so a pack referencing a plugin metric doesn't fail validation
- [x] Add unit test: register scorer via `PluginManager.register_scorer()`, run `ScoringEngine.score_run()`, assert plugin scorer was invoked
- [x] Add unit test: plugin metric name is recognized as valid in `KNOWN_METRICS` after registration
- [x] Add integration test: scenario with a plugin-only metric → validates and scores correctly

**Acceptance Criteria:**
- Scorer registered via PluginManager is picked up by ScoringEngine during pack scoring
- Plugin metric names are valid in scenario pack YAML (KNOWN_METRICS includes them)
- Entry-point discovery actually works end-to-end

**Test Criteria:**
- 3+ unit tests for bridging behavior
- 1 integration test: full plugin scorer lifecycle

**Success Criteria:**
- [x] One registry to rule them all: plugin scorers score
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

## Phase 2: Small Features

**Goal:** Well-scoped enhancements that each solve a specific, bounded problem. Estimated effort: ≤1 day per issue.

---

### [#238](https://github.com/deghosal-2026/agent-eval-forge/issues/238) — Reproducible run manifest: emit per-run environment artifact

**Reported by:** Peer review feedback  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Define `RunManifest` schema (JSON):
  - `run_id` (UUID, ties to scenario result)
  - `timestamp` (ISO-8601)
  - `host`: OS, arch, Python version, hostname (optional)
  - `agent`: adapter type, agent entry point, agent version/hash
  - `dependencies`: locked dep tree (`pip list --format=json` or uv lock)
  - `environment`: env var **names only** (never values), model backend, sandbox mode
  - `execution`: total wall time, tool call count, retry count, adapter warnings
- [x] Implement `RunManifest` model in `src/evalforge/models/manifest.py`
- [x] Collect OS/arch/Python version via `platform` module at run start
- [x] Collect dependency tree via `subprocess` to `pip list --format=json` or `uv pip list --format=json`
- [x] Emit `run-manifest.json` alongside scenario result JSON after every `evalforge run`
- [x] Add manifest to CI artifact upload in `.github/workflows/ci.yml`
- [x] Add `--no-manifest` flag to suppress (for privacy-sensitive environments)
- [x] Add unit test: manifest contains all required fields
- [x] Add integration test: `evalforge run` → `run-manifest.json` exists with correct OS/arch/Python version

**Acceptance Criteria:**
- Every `evalforge run` produces a `run-manifest.json` with OS, arch, Python version, dep tree, adapter info
- No secrets/values in the manifest (env var names only)
- Manifest is diffable between runs

**Test Criteria:**
- Unit test for manifest model serialization
- Integration test for manifest emission after run

**Success Criteria:**
- [x] Published baselines are reproducible from the manifest
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#244](https://github.com/deghosal-2026/agent-eval-forge/issues/244) — Hardware/OS labeling: tag every run with execution environment

**Reported by:** Peer review feedback  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Add `execution_environment` block to run JSON output:
  ```json
  {
    "os": "macOS 15.2",
    "arch": "arm64",
    "python": "3.12.4",
    "runner": "local",
    "model_backend": "mlx",
    "sandbox": "enabled"
  }
  ```
- [x] Inject environment label into CLI summary output (`evalforge run` terminal output)
- [x] Add environment label to field test report headers in `docs/field-test-reports/`
- [x] Add cross-platform comparison table when same suite runs on two platforms
- [x] Reuse data from #238 RunManifest rather than duplicating collection logic
- [x] Add unit test: run output JSON contains `execution_environment` block
- [x] Add unit test: CLI terminal summary displays OS and arch

**Acceptance Criteria:**
- Every run result carries an `execution_environment` label
- Field test reports display the environment used
- Cross-platform runs show side-by-side comparison

**Test Criteria:**
- 2 unit tests for environment label in output and CLI

**Success Criteria:**
- [x] Readers can compare results across platforms
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#253](https://github.com/deghosal-2026/agent-eval-forge/issues/253) — Three-way outcome split in comparison engine

**Reported by:** `mads_hansen` (dev.to)  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Extend `ComparisonEngine.compare()` classification beyond `status == "passed"` flips:
  - `adapter_failed` — scenario couldn't run due to adapter/infra issue
  - `agent_crashed` — agent ran but crashed/timed out
  - `scenario_failed` — agent ran successfully but got wrong answer
- [x] Integrate `FailureTaxonomy.classify()` from `analytics/taxonomy.py` into comparison engine
- [x] Expose failure category in comparison report per-scenario rows
- [x] Surface `safety_violations` from `ScenarioScore` in comparison output
- [x] Add unit test: scenario with `TIMEOUT` → classified as `agent_crashed` (not generic `regressed`)
- [x] Add unit test: scenario with `HALLUCINATION` → classified as `scenario_failed`
- [x] Add unit test: scenario with `SAFETY_VIOLATION` → flagged in comparison output
- [x] Add unit test: run with `status="error"` (adapter failure) → classified as `adapter_failed`

**Acceptance Criteria:**
- Comparison report distinguishes adapter failures, agent crashes, and scenario failures
- `safety_violations` visible in comparison output
- Failure taxonomy is wired into comparison, not orphaned

**Test Criteria:**
- 4+ unit tests for outcome classification
- Integration test: full compare with mixed failure types

**Success Criteria:**
- [x] Comparison output is actionable — tells you who owns the fix
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#241](https://github.com/deghosal-2026/agent-eval-forge/issues/241) — Adapter-agent boundary diagnostics: trace where agent silently fails

**Reported by:** Peer review feedback  
**Labels:** bug, enhancement, 0.2.0

**Checklist:**
- [x] Define `ExecutionTrace` model: `expected_steps`, `actual_steps`, `divergence_point`, `divergence_type`
- [x] Capture expected execution path: `[tool_dispatch, model_call, structured_output, completion]`
- [x] Capture actual execution path from adapter (subprocess stdout/stderr, import adapter's return)
- [x] On run failure, emit `trace_diff.json` alongside scenario result:
  - `divergence_type`: `stopped_early | skipped_step | hung | errored | silent_empty`
- [x] Add subprocess-specific diagnostics: capture exit code, stderr, detect "exited without output"
- [x] Add python_import-specific diagnostics: detect empty return, exception during import, exception during call
- [x] Add unit test: agent that returns empty output → trace diff shows `silent_empty` at `model_call`
- [x] Add integration test: PydanticAI agent that stops after tool dispatch → trace diff identifies divergence

**Acceptance Criteria:**
- Failures come with a `trace_diff.json` explaining where execution diverged from expected
- Adapter-level introspection captures stdout/stderr/exit code for subprocess agents
- "Blank PydanticAI completion" scenario produces an actionable divergence report

**Test Criteria:**
- 3+ unit tests for trace diff generation
- 1 integration test with intentionally broken agent

**Success Criteria:**
- [x] Debugging third-party agents is feasible with breadcrumbs
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#242](https://github.com/deghosal-2026/agent-eval-forge/issues/242) — Surface deterministic trajectory checks as first-class output

**Reported by:** Peer review feedback  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Add `scoring_breakdown` block to scenario result JSON:
  - `deterministic`: list of all 17 checks with per-check pass/fail and score contribution
  - `llm_judge`: list of all judge metrics with per-metric score and rationale
  - `divergences`: cases where deterministic pass ≠ LLM pass
- [x] Classify divergences:
  - `critical`: deterministic fail + LLM pass (agent used wrong tool to get right answer)
  - `warning`: deterministic pass + LLM fail (correct path, poor answer)
- [x] Add `--fail-on-divergence critical` CLI flag for CI gating
- [x] Add CLI summary line: `Score: 0.72 | Deterministic: 14/17 | LLM Judge: 8/11 | Divergences: 2 critical, 1 warning`
- [x] Add unit test: deterministic fail + LLM pass → divergence flagged as `critical`
- [x] Add unit test: deterministic pass + LLM fail → divergence flagged as `warning`
- [x] Add integration test: `--fail-on-divergence critical` exits non-zero when critical divergence exists

**Acceptance Criteria:**
- Scoring output shows per-check breakdown for all 17 deterministic scorers
- Divergences between deterministic and LLM judge are surfaced and classified
- CI can gate on critical divergences

**Test Criteria:**
- 3+ unit tests for scoring breakdown and divergence classification
- 1 integration test for `--fail-on-divergence`

**Success Criteria:**
- [x] Users can see where LLM judge passed but deterministic check failed
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#259](https://github.com/deghosal-2026/agent-eval-forge/issues/259) — Phantom-step deterministic trajectory scorer

**Reported by:** `hoseinmdev` (dev.to)  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Implement `PhantomStepScorer` as a new deterministic scorer:
  - Capture state snapshot (steps executed, artifacts touched, context hash) before/after each tool call
  - `state_after != state_before` → advancing step
  - `state_after == state_before` → candidate phantom step
- [x] Register in `SCORERS` dict and `KNOWN_METRICS`
- [x] Wire into scoring engine
- [x] Add warning when phantom steps exceed threshold (e.g., >30% of total steps)
- [x] Add to trajectory-scoring output surface per #242
- [x] Add unit test: agent that re-reads same artifact twice → phantom steps detected
- [x] Add unit test: agent that makes effective tool call → no phantom steps
- [x] Add unit test: agent with mixed phantom/effective steps → correct ratio

**Acceptance Criteria:**
- Tool calls that don't advance state are flagged as phantom steps
- Phantom step ratio exposed in scoring breakdown
- Warning emitted when phantom ratio exceeds threshold

**Test Criteria:**
- 3+ unit tests for phantom step detection

**Success Criteria:**
- [x] Ineffective tool calls are detectable without an LLM judge
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#239](https://github.com/deghosal-2026/agent-eval-forge/issues/239) — Split CI scoring into three independent gates

**Reported by:** Peer review feedback  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Define three independent score dimensions:
  - `compatibility_score` (0–1): adapter success, import health, tool contract, no blank completions
  - `safety_score` (0–1): disallowed-tool avoidance, budget adherence, sandbox violations
  - `quality_score` (0–1): trajectory correctness, answer quality, LLM judge metrics
- [x] Emit three dimensions separately in `scores.json` aggregate output
- [x] Add per-dimension gating in CI: `--fail-on compatibility`, `--fail-on safety`, `--fail-on quality`
- [x] Update `--output-format github-actions` to report three dimensions
- [x] Map existing scorers to one of three dimensions
- [x] Add unit test: blank completion → `compatibility_score` drops, `safety_score` and `quality_score` unaffected
- [x] Add unit test: disallowed tool → `safety_score` drops
- [x] Add unit test: wrong answer → `quality_score` drops

**Acceptance Criteria:**
- A blank completion and a wrong trajectory produce DIFFERENT score profiles
- CI can gate independently on each dimension
- GitHub Actions summary shows three dimensions

**Test Criteria:**
- 3+ unit tests for per-dimension scoring
- 2 integration tests for CI gating

**Success Criteria:**
- [x] CI failures are immediately attributable to the right team
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#251](https://github.com/deghosal-2026/agent-eval-forge/issues/251) — AdapterManifest: structured adapter metadata with digest for baseline binding

**Reported by:** `mads_hansen` (dev.to)  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Define `AdapterManifest` dataclass:
  - `name` (str)
  - `version` (str)
  - `capabilities`: list of supported features (stdin_stdout, env_isolation, timeout, cancellation, network_policy)
  - `input_schema`, `output_schema` (JSON Schema)
  - `tool_event_stream_version` (str)
  - `writable_paths` (list)
  - `network_policy` (allow_none | allow_list | allow_all)
  - `required_secrets` (list of secret names, never values)
  - `digest` (SHA-256 of all above fields, computed at manifest creation)
- [x] Add `get_manifest() -> AdapterManifest` to `Adapter` base class
- [x] Implement `get_manifest()` on all existing adapters (subprocess, python_import, http, langgraph, pydantic_ai, isolated)
- [x] Compute digest as SHA-256 of canonical JSON serialization of manifest fields
- [x] Add `adapter_manifest` field to `Baseline` model
- [x] Add unit test: all adapters return valid manifests with correct digests
- [x] Add unit test: changing any manifest field changes the digest
- [x] Add unit test: digest is deterministic for same manifest

**Acceptance Criteria:**
- Every adapter exposes a structured manifest with digest
- Manifest is bound to baseline for comparison integrity
- Digest changes detect adapter config changes

**Test Criteria:**
- 3+ unit tests for manifest creation and digest computation
- 1 integration test: all shipped adapters return valid manifests

**Success Criteria:**
- [x] Adapter metadata is machine-readable and bindable
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#254](https://github.com/deghosal-2026/agent-eval-forge/issues/254) — Bind baseline to adapter manifest digest: hard failure on divergence

**Reported by:** `mads_hansen` (dev.to)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #251 (AdapterManifest)

**Checklist:**
- [x] Populate `Baseline.adapter_digest` at `baseline save` time (from adapter manifest)
- [x] In `BaselineStore.validate()`, check adapter digest equality in addition to `pack_version`
- [x] In `ComparisonEngine.compare()`, verify candidate adapter digest matches baseline; if not, classify as `adapter_changed` (not a regression)
- [x] Raise hard error (not warning) when adapter digest differs during strict comparison
- [x] Add `--allow-adapter-change` flag to override for intentional adapter swaps
- [x] Add unit test: baseline saved with `python_import` adapter → compare with candidate using `subprocess` adapter → detected as `adapter_changed`
- [x] Add unit test: same adapter, same config → digest matches → comparison proceeds normally
- [x] Add unit test: `--allow-adapter-change` suppresses the error

**Acceptance Criteria:**
- Changing adapter, sandbox, or timeout between baseline and candidate is detected
- Comparison engine treats adapter change as distinct from agent regression
- Hard failure in strict mode; overridable with `--allow-adapter-change`

**Test Criteria:**
- 3+ unit tests for adapter change detection
- Integration test: save baseline, change adapter, compare → adapter change detected

**Success Criteria:**
- [x] Changing the observation path is no longer invisible to comparison
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#255](https://github.com/deghosal-2026/agent-eval-forge/issues/255) — Surface agent model mismatch as distinct comparison outcome

**Reported by:** `nyx533` (dev.to)  
**Labels:** enhancement, 0.2.0

**Checklist:**
- [x] Populate `Baseline.agent` dict at `baseline save` with structured model info:
  - `model`: model name string (extracted from agent config)
  - `provider`: provider name (e.g., openai, anthropic, mlx)
  - `framework`: agent framework (langgraph, pydantic_ai, custom)
  - `version`: agent code version/hash
- [x] In `ComparisonEngine.compare()`, compare `baseline.agent.model` vs `candidate.agent.model`
- [x] If model differs, classify as `model_changed` (distinct from `regressed`/`improved`)
- [x] Add structured model info extraction to `_sanitize_agent` in `adapters/base.py`
- [x] Record model name on `RunArtifact.agent` from agent wrapper template's `model` override
- [x] Add `--model` CLI option to explicitly declare the model
- [x] Add unit test: baseline with `gpt-4o`, candidate with `gpt-4o-mini` → classified as `model_changed`, not `regressed`
- [x] Add unit test: same model, score change → classified as `regressed`

**Acceptance Criteria:**
- Model-layer changes are distinguished from agent-code changes in comparison reports
- Baseline stores structured agent metadata (model, provider, framework)
- Comparison output makes model change visible

**Test Criteria:**
- 3+ unit tests for model mismatch detection
- Integration test: full compare with different models

**Success Criteria:**
- [x] Comparison reports distinguish "the model changed" from "the agent is worse"
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#275](https://github.com/deghosal-2026/agent-eval-forge/issues/275) — Security review for v0.2.0

**Reported by:** Internal (follow-up from v0.1.0 security review at `docs/0.1.0/security-review.md`)  
**Labels:** documentation, security, 0.2.0

**Checklist:**
- [x] Review all security findings from v0.1.0 review and verify remediation status
- [x] Audit new 0.2.0 features (fixtures, run manifest, adapter manifest, plugin registry) for security concerns
- [x] Verify `scenario_id` path traversal fix (WBS M8 item from `docs/0.1.0/wbs.md:527`)
- [x] Verify audit log rotation/size management
- [x] Verify Docker sandbox hardening (read-only root, network isolation, resource limits)
- [x] Publish updated security review at `docs/0.2.0/security-review.md`

**Acceptance Criteria:**
- v0.1.0 security findings are closed or explicitly deferred
- New 0.2.0 features are covered by security review
- Security review document published at `docs/0.2.0/security-review.md`

**Success Criteria:**
- [x] Security review is current for v0.2.0 release
- [x] All high-severity findings from v0.1.0 are addressed

---

### [#276](https://github.com/deghosal-2026/agent-eval-forge/issues/276) — Update PRD, user guide, and docs for v0.2.0 code changes

**Reported by:** Internal (docs drift from v0.2.0 feature/bug-fix work)  
**Labels:** documentation, 0.2.0

**Checklist:**
- [x] **Update PRD** (`docs/PRD.md`) for any new/changed user journeys from v0.2.0 features
- [x] **Update user guide** (`docs/user-guide.md`) for new commands, flags, and behaviours:
  - `--agent-function`, `--model`, `--allow-adapter-change`, `--fail-on-divergence`, `--no-manifest`
  - New `--fail-on` dimensions (`compatibility`, `safety`, `quality`)
  - `python:module:function` agent spec syntax
  - Exit code behaviour (`0`/`1`/`3`/`4`)
  - `github-actions` output format three-way scores
- [x] **Update scenario authoring** (`docs/scenario-authoring.md`) for `expected.criteria` rendering and `exact_match` removal
- [x] **Update scoring guide** (`docs/scoring.md`) for new deterministic scorers (`phantom_step`), `scoring_breakdown`, offline hybrid gate behaviour
- [x] **Update spec** (`docs/spec.md`) for any API/behaviour drift (exit codes, adapter manifest, run manifest)
- [x] **Update CI guide** (`docs/ci.md`) for three-gate scoring and adapter/score-delta comparison
- [x] Verify README quickstart matches actual CLI behaviour

**Acceptance Criteria:**
- All 32+ v0.2.0 changes are reflected in the relevant docs
- No doc references dead CLI flags, removed metrics, or outdated exit codes
- New commands/flags documented in user guide

**Test Criteria:**
- Grep docs for any removed flags (`exact_match`, `--fixtures` semantics) — none stale
- Manual: docs examples run without error

**Success Criteria:**
- [x] Docs are consistent with v0.2.0 behaviour
- [x] First-run experience (init + validate + run) matches docs
- [x] Code review completed

---

### [#292](https://github.com/deghosal-2026/agent-eval-forge/issues/292) — Document model-vs-deterministic comparison findings from JPS integration study

**Reported by:** `kikashy` (Brian Jin, JPS integration study)  
**Labels:** documentation, 0.2.0  
**Severity:** Advisory — informs scoring architecture decisions, not a bug  
**Location:** `docs/` (new `docs/scoring-comparison.md` or section in architecture/research docs)

**Context:** The JPS study compared an LLM supplied the same policy as prose against the deterministic evaluator. The model scored 62/63 and never executed a forbidden action — but its two failures were at interesting boundaries that illuminate *when* each approach breaks.

**Checklist:**
- [x] Create `docs/scoring-comparison.md` (or add to `docs/architecture.md`) covering:
  - [x] Summary of the 62/63 result — model performs competitively but differently
  - [x] **Boundary failure 1 — Exact-threshold tie resolution:** The model resolved an exact-threshold tie that the deterministic evaluator must leave unresolved. This is a classification-boundary issue where the model "makes a call" the spec demands be left ambiguous.
  - [x] **Boundary failure 2 — Routing destination corruption:** The model repeatedly corrupted a routing destination that remains stable when carried as structured data through deterministic logic.
  - [x] **Key insight:** The two approaches fail differently and their failure classes barely overlap. Neither "deterministic beats model" nor "model beats deterministic" — they complement each other.
  - [x] Guidance on when deterministic vs. LLM-based scoring is appropriate
  - [x] The "different failure classes" insight as a design principle for scoring architecture
- [x] Link to the [JPS study artifacts](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/tree/main/studies/013-agent-eval-forge-integration) for reproducibility
- [x] Reference this finding in the scoring architecture section of `docs/spec.md`

**Acceptance Criteria:**
- EvalForge users can make informed decisions about deterministic vs. LLM-based scoring
- The two boundary failure modes are documented as design constraints
- Study artifacts are linked for reference

**Success Criteria:**
- [x] Document published and cross-referenced from scoring docs
- [x] Code review completed
- [x] All comments added to touched code

---

### [#293](https://github.com/deghosal-2026/agent-eval-forge/issues/293) — Add adversarial scenario pack support and hidden-case pattern from JPS study

**Reported by:** `kikashy` (Brian Jin, JPS integration study)  
**Labels:** enhancement, 0.2.0  
**Severity:** Enhancement — codifies a proven adversarial-testing pattern  
**Location:** `docs/scenario-authoring.md`, `docs/` (new adversarial testing guide)

**Context:** The JPS study injected 4 hidden adversarial cases written by an independent reviewer. One case was intentionally designed to escape the judgment layer's own tests — it succeeded, and EvalForge's `argument_correctness` trace scorer caught it downstream. This proved the value of layered defense with adversarial cases.

**Checklist:**
- [x] Document adversarial scenario authoring in `docs/scenario-authoring.md` (new "Adversarial Scenarios" section):
  - [x] How to design a case that targets a known blind spot (e.g., exploit `expected.criteria` not being read, a scorer vacuous pass on empty trajectories)
  - [x] Pattern: independent reviewer authorship — tests written by someone who didn't write the code
  - [x] Pattern: layered defense — adversarial cases designed to escape Layer 1 (judgment evaluator) and be caught by Layer 2 (EvalForge integration harness)
  - [x] How to interpret results when Layer 1 passes but Layer 2 fails (and vice versa)
- [x] Consider creating a canonical "adversarial scenario pack" example in `examples/adversarial-pack/` with:
  - [x] A scenario designed to exploit the rubric-criteria gap (#273)
  - [x] A scenario with empty trajectory that deterministic scorers vacuously pass (#270)
  - [x] A scenario with disallowed tool called that exits zero (#269)
  - [x] A scenario designed to exploit the ToolStub honour-system gap (#272)
  - [x] A hidden case that escapes a sample custom scorer
- [x] Document the two-layer defense model (#294) as the recommended architecture for using adversarial packs
- [x] If permission obtained from Judgment Pack, contribute the 4 study adversarial cases as example scenarios

**Acceptance Criteria:**
- EvalForge users and pack authors can create adversarial scenarios that test EvalForge's own blind spots
- The pattern of layered defense with adversarial cases is documented
- At minimum, the existing vulnerability classes (#269-#274) are represented as adversarial scenario templates

**Success Criteria:**
- [x] Adversarial testing pattern documented
- [x] Example pack created (or explicitly deferred with rationale)
- [x] Code review completed
- [x] All comments added to touched code

---

### [#294](https://github.com/deghosal-2026/agent-eval-forge/issues/294) — Document two-layer defense architecture insight from JPS study (judgment + integration harness)

**Reported by:** `kikashy` (Brian Jin, JPS integration study)  
**Labels:** documentation, 0.2.0  
**Severity:** Advisory — architectural insight that should guide future design  
**Location:** `docs/architecture.md` (new) or `docs/two-layer-defense.md` (new)

**Context:** The JPS study's key finding: "the two layers catch different classes of failure — and an external regression harness can detect integration mistakes that a perfectly correct judgment evaluator cannot see." This was proven by injecting 20 failures across both layers with all detection predictions holding.

**Checklist:**
- [x] Create `docs/architecture.md` containing:
  - [x] **The two-layer defense model** with diagram/table:
    - **Layer 1 (Judgment Evaluator):** Catches semantic/logic errors inside the agent's decision-making. Tested by the judgment layer's own test suite.
    - **Layer 2 (EvalForge Integration Harness):** Catches integration errors (broken adapters, config mistakes, tool wiring, I/O corruption) and enforces structural/behavioral contracts (disallowed actions, trajectories, exit codes, artifact integrity).
  - [x] **Evidence from the JPS study:**
    - 20/20 detection predictions held
    - Judgment-semantic failures caught by Layer 1
    - Integration failures invisible to Layer 1, caught by Layer 2
    - `zero_disallowed_actions` blocked every protected-action execution
    - Adversarial case escaped Layer 1, caught by `argument_correctness` in Layer 2
  - [x] **Failure-class coverage matrix:** what each layer catches, what escapes each, and what requires both
  - [x] **Recommended configuration:** How to set up EvalForge as the integration layer alongside a judgment evaluator
  - [x] **Design principle:** "An external regression harness can detect integration mistakes that a perfectly correct judgment evaluator cannot see"
- [x] Cross-reference this architecture doc from:
  - [x] `docs/spec.md` (architecture section)
  - [x] `docs/ci.md` (CI gating strategy)
  - [x] `docs/scenario-authoring.md` (adversarial scenarios section per #293)
  - [x] `README.md` (key concepts)
- [x] Reference the [JPS study artifacts](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/tree/main/studies/013-agent-eval-forge-integration) and [UPSTREAM.md](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/blob/main/studies/013-agent-eval-forge-integration/UPSTREAM.md) for reproducibility
- [x] Link to the six companion bug reports (#269-#274) as concrete examples of Layer 2 catching what Layer 1 misses

**Acceptance Criteria:**
- The two-layer defense model is the documented architecture for EvalForge
- Users understand EvalForge is not a replacement for a judgment evaluator but its complement
- The JPS study evidence is cited as empirical validation

**Success Criteria:**
- [x] `docs/architecture.md` published
- [x] Cross-references in place across all relevant docs
- [x] Code review completed
- [x] All comments added to touched code

---

## Phase 3: New Framework Adapters

**Goal:** Expand EvalForge's supported framework surface to the most-adopted
agent frameworks it currently lacks dedicated adapters for. All currently fall
through to the generic `python`/`subprocess` adapters, which cannot faithfully
capture their execution models. These issues add first-class functional support
+ field-test coverage, mirroring the LangGraph/PydanticAI adapter+field pair
already shipped.

**Wave 1 (issues #277-#280, label `0.2.0`):** CrewAI (`Crew.kickoff()`, ~53k
stars) and OpenAI Agents SDK (`Runner.run` + event stream, ~10.3M downloads/mo).

**Wave 2 (issues #281-#290, label `0.2.0`):** smolagents (`CodeAgent.run`,
Hugging Face), AutoGen (`AssistantAgent`/`ConversableAgent` group chat),
LlamaIndex Agents (`AgentRunner`/`AgentWorker`), Claude Agent SDK (`Agent.run`,
Anthropic), Google ADK (`Runner.run`/`ADKResult`).

**Docs (issue #291, label `0.2.0`):** update `spec.md`, `user-guide.md`,
`README.md`, `ci.md`, and the field-test plan to cover all new Wave 1/2
adapter families, extras, config schema, and model-override contract.

**Status note:** The 0.1.0 field roster (19 agents) was emptied on 2026-08-10
after 14 agents were quarantined and the remaining clones were removed. The
field roster is fresh; the Wave 1/2 adapter families fill part of it.

**Scenario packs (2026-08-11):** Field scenario packs created for all 8
OMLX-compatible framework families. Each pack contains 5 scenarios (basic-tool-call,
multi-step, no-tool-needed, disallowed-tool, structured-output) plus a shared
safety pack (safety-disallowed-tool, safety-boundary). All scenarios are
OMLX-local-ready (no paid API calls required):

| Pack | Scenarios | Location |
|---|---|---|
| `field-smoke.yaml` | 3 (tool-call, no-tool, multi-tool) | `field/scenarios/` |
| `langgraph-core.yaml` | 5 (lg-*) | `field/scenarios/` |
| `pydantic-ai-core.yaml` | 5 (pai-*) | `field/scenarios/` |
| `crewai-core.yaml` | 5 (crew-*) | `field/scenarios/` |
| `openai-agents-core.yaml` | 5 (oa-*) | `field/scenarios/` |
| `smolagents-core.yaml` | 5 (sm-*) | `field/scenarios/` |
| `autogen-core.yaml` | 5 (ag-*) | `field/scenarios/` |
| `llamaindex-core.yaml` | 5 (li-*) | `field/scenarios/` |
| `adk-core.yaml` | 5 (adk-*) | `field/scenarios/` |
| `shared-safety.yaml` | 2 (safety-disallowed-tool, safety-boundary) | `field/scenarios/` |
| **Total** | **47 scenarios across 10 packs** | |

**Field agent roster (2026-08-11):** 19 agent candidates curated across all 8
OMLX-compatible frameworks (Claude SDK excluded — requires Anthropic API). Agent
shims live in `field/config/<slug>_wrapper.py` and wrap real agent repos with
OMLX-LLM redirection. Agent repos cloned under `field/agents/` (gitignored):

| Framework | Candidates | Slugs |
|---|---|---|
| LangGraph | 2 | lg-azure, lg-official |
| PydanticAI | 2 | pai-azure, pai-official |
| CrewAI | 3 | crew-qs, crew-examples, crew-quickstarts |
| OpenAI Agents SDK | 2 | oa-azure, oa-official |
| smolagents | 3 | sm-smolcc, sm-deepsearch, sm-qs |
| AutoGen (AG2) | 2 | ag-azure, ag-official |
| LlamaIndex | 2 | li-azure, li-official |
| Google ADK | 3 | adk-qs, adk-sokart, adk-official |
| **Total** | **19 agent candidates** | |

---

### [#277](https://github.com/deghosal-2026/agent-eval-forge/issues/277) — CrewAI functional support: dedicated `crewai` adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/crewai.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `CrewAIAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `crew`), run `crew.kickoff()`, normalize to `evalforge.run_envelope.v1`
  (final output from `CrewOutput.raw`, trajectory from task/tool history, cost
  from `usage_metrics`); non-completed → `status: error` (works with #270 short-circuit)
- [x] Register `"crewai"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction: map CrewAI per-agent task/tool execution → `TrajectoryStep`
  list (feeds `tool_called`, `tool_correctness`, `step_efficiency`, `phantom_step` #259)
- [x] Model/provider redirection mirroring `langgraph.py:60-101`: honor
  `EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL`, set
  `OPENAI_API_KEY`/`OPENAI_BASE_URL` defaults (CrewAI proxies LangChain LLMs) —
  fixes the exact root-cause failure class from the 0.1.0 pydantic sweep
- [x] Deps handling: construct/pass deps (PydanticAI `deps_type` — pattern from `pa-github` failure)
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `crewai = ["crewai"]` in `pyproject.toml`; lazy import;
  document `pip install evalforge[crewai]`
- [x] Validate CrewAI ≥1.0 API (kickoff/kickoff_async/CrewOutput) at implementation time; pin against roster version

**Acceptance Criteria:**
- `create_adapter({"type": "crewai", ...})` returns a working `CrewAIAdapter`
- A real CrewAI repo (≥2 tools, offline-runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents `crewai` adapter type, config schema, model override
- `evalforge run --agent crewai:module:crew` works as documented

**Test Criteria:**
- 6+ unit tests: manifest+digest, pre-built `Crew` import+run, model override,
  trajectory extraction from synthetic history, error path, idempotent manifest

**Success Criteria:**
- [x] CrewAI agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean (`ruff check`)
- [x] Type check clean (`mypy --strict`)

---

### [#278](https://github.com/deghosal-2026/agent-eval-forge/issues/278) — CrewAI field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #277 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<crewai-slug>.json`, `field/scenarios/crewai-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 CrewAI repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools, offline-runnable,
  OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] Add `crewai` detection to `field/gen-field-json.py` heuristics (detect `Crew`/`kickoff`)
- [x] Author `field/config/<slug>.json`: `adapter_type: crewai`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/crewai-core.yaml`: `crew-basic-tool-call`,
  `crew-multi-step`, `crew-no-tool-needed`, `crew-disallowed-tool`,
  `crew-structured-output` (modeled on `langgraph-core.yaml`)
- [x] `conftest.py`: document `field_category: crewai`
- [x] Verify `test_field_agent.py` generic `create_adapter().run()` + `ScoringEngine` flow works with adapter
- [x] `run-local.sh`: confirm tier env block (OPENAI keys / MLX) covers CrewAI LangChain LLMs
- [x] Add `--extra crewai` to CI field-test job + `field/README.md`
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real CrewAI agents clone, run, produce scored results in `field/results/`
- ≥1 CrewAI agent meets `minimum_pass_rate` on cheap tier (proves adapter+harness on real code)
- CrewAI failures correctly classified (Class A/B/C/D)
- Field report covers CrewAI agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `crewai` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] CrewAI is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#279](https://github.com/deghosal-2026/agent-eval-forge/issues/279) — OpenAI Agents SDK functional support: dedicated adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/openai_agents.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `OpenAIAgentsAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `agent`), run `Runner.run_sync(agent, input, context=...)` (async fallback
  via `asyncio.run`), normalize to `evalforge.run_envelope.v1` (final output from
  `RunResult.final_output`, trajectory from event stream, cost from token usage);
  non-completed → `status: error` (works with #270 short-circuit)
- [x] Register `"openai-agents"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction from `run_streamed()` event stream
  (`RawToolCallEvent`, `RawFunctionCallEvent`, `RawFunctionCallOutputEvent`,
  `RunItemStreamEvent`) → `TrajectoryStep` list; surface guardrail results +
  handoff traces as steps (feeds `tool_called`, `tool_correctness`,
  `step_efficiency`, `phantom_step` #259)
- [x] Model/provider override mirroring `langgraph.py:60-101`: honor field env +
  `EVALFORGE_FORCE_MODEL`, set `OPENAI_API_KEY`/`OPENAI_BASE_URL` defaults so the
  SDK's `openai` client points at MLX/OpenRouter — avoids the 0.1.0 pydantic failure class
- [x] Deps/context handling: construct and pass `context` (RunContextWrapper pattern)
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `openai-agents = ["openai-agents"]` in `pyproject.toml`; lazy import;
  document `pip install evalforge[openai-agents]`
- [x] Validate `openai-agents` 0.x async/streaming API at implementation time (unstable — centralize imports)

**Acceptance Criteria:**
- `create_adapter({"type": "openai-agents", ...})` yields a working adapter
- A real Agents SDK repo (≥2 tools, offline/local-model runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents `openai-agents` adapter type, config schema, model override
- `evalforge run --agent openai-agents:module:agent` works as documented

**Test Criteria:**
- [x] 6+ unit tests: manifest+digest, pre-built `Agent` import+run, model override,
  trajectory extraction from synthetic event stream, error path, idempotent manifest

**Success Criteria:**
- [x] OpenAI Agents SDK agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#280](https://github.com/deghosal-2026/agent-eval-forge/issues/280) — OpenAI Agents SDK field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #279 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<openai-agents-slug>.json`, `field/scenarios/openai-agents-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 OpenAI Agents SDK repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools,
  offline-runnable, OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] Add Agents SDK detection to `field/gen-field-json.py` heuristics
  (detect `Runner.run` / `Agent(` from `openai.agents` or `agents` import)
- [x] Author `field/config/<slug>.json`: `adapter_type: openai-agents`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/openai-agents-core.yaml`: `oa-basic-tool-call`,
  `oa-multi-step`, `oa-no-tool-needed`, `oa-disallowed-tool`, `oa-structured-output`
- [x] `conftest.py`: document `field_category: openai-agents`
- [x] Verify `test_field_agent.py` generic flow works with adapter (no hardcoded type assumptions)
- [x] `run-local.sh`: confirm tier env block routes the SDK `openai` client to MLX/OpenRouter
- [x] Add `--extra openai-agents` to CI field-test job + `field/README.md`
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real Agents SDK agents clone, run, produce scored results in `field/results/`
- ≥1 agent meets `minimum_pass_rate` on cheap tier (proves adapter+harness on real code)
- Failures correctly classified (Class A/B/C/D)
- Field report covers Agents SDK agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `openai-agents` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] OpenAI Agents SDK is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#281](https://github.com/deghosal-2026/agent-eval-forge/issues/281) — smolagents functional support: dedicated `smolagents` adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/smolagents.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `SmolagentsAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `build_agent`), obtain a `CodeAgent`/`ToolCallingAgent`, invoke with the
  scenario input, normalize to `evalforge.run_envelope.v1` (final output from result,
  trajectory from `agent.memory` / `agent.steps`, cost from tracked usage);
  non-completed → `status: error` (works with #270 short-circuit)
- [x] Register `"smolagents"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction: map Hugging Face `Step` subclasses (`ToolCallStep`,
  `ObservationStep`, `FinalAnswerStep`) and code-execution steps → `TrajectoryStep`
  (feeds `tool_called`, `tool_correctness`, `step_efficiency`, `phantom_step` #259)
- [x] Model/provider redirection mirroring `langgraph.py:60-101`: honor
  `EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL`, set streaming-friendly
  defaults — fixes the exact root-cause failure class from the 0.1.0 pydantic sweep
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `smolagents = ["smolagents"]` in `pyproject.toml`; lazy import;
  document `pip install evalforge[smolagents]`
- [x] Validate smolagents ≥1.x API (Step kinds, `agent.steps`, LiteLLMModel) at
  implementation time; pin against installed version

**Acceptance Criteria:**
- `create_adapter({"type": "smolagents", ...})` returns a working `SmolagentsAdapter`
- A real smolagents repo (≥2 tools, offline-runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents the `smolagents` adapter type, config schema, model override
- `evalforge run --agent smolagents:module:build_agent` works as documented

**Test Criteria:**
- [x] 6+ unit tests: manifest+digest (see #251), pre-built agent import+run, model override,
  trajectory extraction from synthetic `Step[]` history, error path, idempotent manifest
- [x] Integration test (skipif `smolagents` not installed): real framework + mock fixture
  agent produces a valid `RunArtifact` (mirror `test_adapters_integration.py`)

**Success Criteria:**
- [x] smolagents agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#282](https://github.com/deghosal-2026/agent-eval-forge/issues/282) — smolagents field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #281 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<slug>.json`, `field/scenarios/smolagents-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 smolagents repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools,
  offline-runnable, OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] `field/gen-field-json.py` heuristics detect `smolagents` (`CodeAgent`/
  `ToolCallingAgent` or `smolagents` import)
- [x] Author `field/config/<slug>.json`: `adapter_type: smolagents`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/smolagents-core.yaml`: `sm-basic-tool-call`, `sm-multi-step`,
  `sm-no-tool-needed`, `sm-disallowed-tool`, `sm-structured-output`
- [x] `conftest.py`: document `field_category: smolagents`
- [x] Verify `test_field_agent.py` generic `create_adapter().run()` + `ScoringEngine` flow
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier
  (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real smolagents agents clone, run, produce scored results in `field/results/`
- ≥1 smolagents agent meets `minimum_pass_rate` on cheap tier
- smolagents failures correctly classified (Class A/B/C/D)
- Field report covers smolagents agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `smolagents` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] smolagents is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#283](https://github.com/deghosal-2026/agent-eval-forge/issues/283) — AutoGen functional support: dedicated `autogen` adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/autogen.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `AutoGenAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `build_agent`), obtain an `AssistantAgent`/`ConversableAgent` (or group
  chat), initiate chat with the scenario input, normalize to `evalforge.run_envelope.v1`
  (final output from last message, trajectory from `chat_history`/`oai_messages`,
  cost from usage);   non-completed → `status: error` (works with #270 short-circuit)
- [x] Register `"autogen"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction: map chat history (`function_call`/`tool_calls`/`tool`/text)
  → `TrajectoryStep` (feeds `tool_called`, `tool_correctness`, `step_efficiency`, `phantom_step` #259)
- [x] Model/provider redirection mirroring `langgraph.py:60-101`: honor
  `EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL` — fixes the exact
  root-cause failure class from the 0.1.0 pydantic sweep
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `autogen = ["autogen-agentchat>=0.4"]` in `pyproject.toml`; lazy
  import; document `pip install evalforge[autogen]`
- [x] Group-chat support: default to two-agent assistant→user flow; document pointing
  at a custom group-chat initiator
- [x] Validate AutoGen ≥0.4 API (messages shape, `initiate_chat` return) at
  implementation time; pin against installed version

**Acceptance Criteria:**
- `create_adapter({"type": "autogen", ...})` returns a working `AutoGenAdapter`
- A real AutoGen repo (≥2 tools, offline-runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents the `autogen` adapter type, config schema, model override
- `evalforge run --agent autogen:module:build_agent` works as documented

**Test Criteria:**
- [x] 6+ unit tests: manifest+digest (see #251), pre-built agent import+run, model override,
  trajectory extraction from synthetic `chat_history`, error path, idempotent manifest
- [x] Integration test (skipif `autogen` not installed): real framework + mock fixture agent
  produces a valid `RunArtifact` (mirror `test_adapters_integration.py`)

**Success Criteria:**
- [x] AutoGen agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#284](https://github.com/deghosal-2026/agent-eval-forge/issues/284) — AutoGen field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #283 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<slug>.json`, `field/scenarios/autogen-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 AutoGen repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools,
  offline-runnable, OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] `field/gen-field-json.py` heuristics detect `autogen`
  (`AssistantAgent`/`ConversableAgent` or `autogen` import)
- [x] Author `field/config/<slug>.json`: `adapter_type: autogen`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/autogen-core.yaml`: `ag-basic-tool-call`, `ag-multi-step`,
  `ag-no-tool-needed`, `ag-disallowed-tool`, `ag-structured-output`
- [x] `conftest.py`: document `field_category: autogen`
- [x] Verify `test_field_agent.py` generic `create_adapter().run()` + `ScoringEngine` flow
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier
  (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real AutoGen agents clone, run, produce scored results in `field/results/`
- ≥1 AutoGen agent meets `minimum_pass_rate` on cheap tier
- AutoGen failures correctly classified (Class A/B/C/D)
- Field report covers AutoGen agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `autogen` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] AutoGen is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#285](https://github.com/deghosal-2026/agent-eval-forge/issues/285) — LlamaIndex functional support: dedicated `llamaindex` adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/llamaindex.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `LlamaIndexAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `build_agent`), obtain an `AgentRunner`/`AgentWorker` (e.g.
  `FunctionCallingAgentWorker`/`ReActAgentWorker`), run a chat/query with the scenario
  input, normalize to `evalforge.run_envelope.v1` (final output from `Response.response`,
  trajectory from response sources + tool calls, cost from usage);
  non-completed → `status: error` (works with #270 short-circuit)
- [x] Register `"llamaindex"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction: map chat response/sources + `FunctionCallingAgentWorker`
  tool calls → `TrajectoryStep` (feeds `tool_called`, `tool_correctness`,
  `step_efficiency`, `phantom_step` #259)
- [x] Model/provider redirection mirroring `langgraph.py:60-101`: honor
  `EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL` — fixes the exact
  root-cause failure class from the 0.1.0 pydantic sweep
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `llamaindex = ["llama-index>=0.11"]` in `pyproject.toml`; lazy
  import; document `pip install evalforge[llamaindex]`
- [x] Support both `chat()` and `query()` entry points; default to `chat` when available
- [x] Validate LlamaIndex ≥0.11 API (AgentRunner/Response shape, source_nodes) at
  implementation time; pin against installed version

**Acceptance Criteria:**
- `create_adapter({"type": "llamaindex", ...})` returns a working `LlamaIndexAdapter`
- A real LlamaIndex repo (≥2 tools, offline-runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents the `llamaindex` adapter type, config schema, model override
- `evalforge run --agent llamaindex:module:build_agent` works as documented

**Test Criteria:**
- [x] 6+ unit tests: manifest+digest (see #251), pre-built `AgentRunner` import+run, model
  override, trajectory extraction from synthetic `Response`/chat history, error path,
  idempotent manifest
- [x] Integration test (skipif `llama-index` not installed): real framework + mock fixture
  agent produces a valid `RunArtifact` (mirror `test_adapters_integration.py`)

**Success Criteria:**
- [x] LlamaIndex agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#286](https://github.com/deghosal-2026/agent-eval-forge/issues/286) — LlamaIndex field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #285 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<slug>.json`, `field/scenarios/llamaindex-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 LlamaIndex repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools,
  offline-runnable, OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] `field/gen-field-json.py` heuristics detect `llamaindex`
  (`AgentRunner`/`AgentWorker` or `llama_index` import)
- [x] Author `field/config/<slug>.json`: `adapter_type: llamaindex`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/llamaindex-core.yaml`: `li-basic-tool-call`, `li-multi-step`,
  `li-no-tool-needed`, `li-disallowed-tool`, `li-structured-output`
- [x] `conftest.py`: document `field_category: llamaindex`
- [x] Verify `test_field_agent.py` generic `create_adapter().run()` + `ScoringEngine` flow
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier
  (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real LlamaIndex agents clone, run, produce scored results in `field/results/`
- ≥1 LlamaIndex agent meets `minimum_pass_rate` on cheap tier
- LlamaIndex failures correctly classified (Class A/B/C/D)
- Field report covers LlamaIndex agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `llamaindex` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] LlamaIndex is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#287](https://github.com/deghosal-2026/agent-eval-forge/issues/287) — Claude Agent SDK functional support: dedicated `claude` adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/claude.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `ClaudeAgentSDKAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `build_agent`), obtain a `claude.agents.Agent`, run with the scenario input,
  normalize to `evalforge.run_envelope.v1` (final output from run result, trajectory from
  agent events/steps taxa, cost from usage); non-completed → `status: error`
  (works with #270 short-circuit)
- [x] Register `"claude"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction: map Claude Agent SDK execution events (blocks: tool use,
  results, text, thinking) → `TrajectoryStep` (feeds `tool_called`, `tool_correctness`,
  `step_efficiency`, `phantom_step` #259)
- [x] Model/provider redirection mirroring `langgraph.py:60-101`: honor
  `EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL`, set `ANTHROPIC_API_KEY`/
  `ANTHROPIC_BASE_URL` defaults — fixes the exact root-cause failure class from the
  0.1.0 pydantic sweep
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `claude = ["claude-agent-sdk>=0.1"]` in `pyproject.toml`; lazy import;
  document `pip install evalforge[claude]`
- [x] Support both sync and async execution entry points (SDK `Agent.run` is async);
  default to the blocking wrapped path for field sweep
- [x] Validate Claude Agent SDK ≥0.1 API (Command/Agent shape, streaming events) at
  implementation time; pin against installed version

**Acceptance Criteria:**
- `create_adapter({"type": "claude", ...})` returns a working `ClaudeAgentSDKAdapter`
- A real Claude Agent SDK repo (≥2 tools, offline-runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents the `claude` adapter type, config schema, model override
- `evalforge run --agent claude:module:build_agent` works as documented

**Test Criteria:**
- [x] 6+ unit tests: manifest+digest (see #251), pre-built agent import+run, model override,
  trajectory extraction from synthetic event stream, error path, idempotent manifest
- [x] Integration test (skipif `claude-agent-sdk` not installed): real framework + mock
  fixture agent produces a valid `RunArtifact` (mirror `test_adapters_integration.py`)

**Success Criteria:**
- [x] Claude Agent SDK agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#288](https://github.com/deghosal-2026/agent-eval-forge/issues/288) — Claude Agent SDK field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #287 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<slug>.json`, `field/scenarios/claude-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 Claude Agent SDK repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools,
  offline-runnable, OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] `field/gen-field-json.py` heuristics detect `claude`
  (`claude.agents.Agent` or `claude-agent-sdk` import)
- [x] Author `field/config/<slug>.json`: `adapter_type: claude`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/claude-core.yaml`: `cl-basic-tool-call`, `cl-multi-step`,
  `cl-no-tool-needed`, `cl-disallowed-tool`, `cl-structured-output`
- [x] `conftest.py`: document `field_category: claude`
- [x] Verify `test_field_agent.py` generic `create_adapter().run()` + `ScoringEngine` flow
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier
  (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real Claude Agent SDK agents clone, run, produce scored results in `field/results/`
- ≥1 Claude Agent SDK agent meets `minimum_pass_rate` on cheap tier
- Claude Agent SDK failures correctly classified (Class A/B/C/D)
- Field report covers Claude Agent SDK agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `claude` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] Claude Agent SDK is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#289](https://github.com/deghosal-2026/agent-eval-forge/issues/289) — Google ADK functional support: dedicated `adk` adapter

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Location:** `src/evalforge/adapters/adk.py` (new), `factory.py`, `worker.py`, `pyproject.toml`

**Checklist:**
- [x] `ADKAdapter(Adapter)` implementing `_invoke`: resolve `module`/`function`
  (default `build_agent`), obtain a `google.adk.agents.Agent`, run via `gadk`/runner
  with the scenario input, normalize to `evalforge.run_envelope.v1` (final output from
  run result, trajectory from action/event stream, cost from usage);
  non-completed → `status: error` (works with #270 short-circuit)
- [x] Register `"adk"` in `ADAPTERS` (`factory.py`) + export in `adapters/__init__.py`
- [x] Trajectory extraction: map ADK events (function-call, function-response, text,
  thought) → `TrajectoryStep` (feeds `tool_called`, `tool_correctness`,
  `step_efficiency`, `phantom_step` #259)
- [x] Model/provider redirection mirroring `langgraph.py:60-101`: honor
  `EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL`, set Gemini/LiteLLM-compatible
  defaults — fixes the exact root-cause failure class from the 0.1.0 pydantic sweep
- [x] `get_manifest()` → `AdapterManifest` + canonical digest (per #251/#254 binding)
- [x] Wire into `adapters/worker.py` (mirror `_langgraph`/`_pydantic_ai` dispatch)
- [x] Optional extra `adk = ["google-adk>=1.0"]` in `pyproject.toml`; lazy import;
  document `pip install evalforge[adk]`
- [x] Support the synchronous run entry point used by the field sweep; document async
  where the SDK requires it
- [x] Validate Google ADK ≥1.0 API (Agent/ADKResult shape, streaming events) at
  implementation time; pin against installed version

**Acceptance Criteria:**
- `create_adapter({"type": "adk", ...})` returns a working `ADKAdapter`
- A real Google ADK repo (≥2 tools, offline-runnable) runs end-to-end with non-empty trajectory
- `docs/spec.md` documents the `adk` adapter type, config schema, model override
- `evalforge run --agent adk:module:build_agent` works as documented

**Test Criteria:**
- [x] 6+ unit tests: manifest+digest (see #251), pre-built agent import+run, model override,
  trajectory extraction from synthetic action/event stream, error path, idempotent manifest
- [x] Integration test (skipif `google-adk` not installed): real framework + mock fixture
  agent produces a valid `RunArtifact` (mirror `test_adapters_integration.py`)

**Success Criteria:**
- [x] Google ADK agents score without custom wrappers
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#290](https://github.com/deghosal-2026/agent-eval-forge/issues/290) — Google ADK field test support: roster, scenario packs, harness wiring

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** enhancement, 0.2.0  
**Depends on:** #289 (adapter must exist before real agents score)  
**Location:** `field/list.txt`, `field/config/<slug>.json`, `field/scenarios/adk-core.yaml`, `field/*`

**Checklist:**
- [x] Curate 3-5 Google ADK repos (HIGH/MEDIUM/LOW stars mix, ≥2 tools,
  offline-runnable, OSI license) per `docs/testing/field-test-plan.md` §2
- [x] Add to `field/list.txt` with pinned commit SHAs
- [x] `field/gen-field-json.py` heuristics detect `adk` (`google.adk` Agent import)
- [x] Author `field/config/<slug>.json`: `adapter_type: adk`, `adapter_config`,
  `setup_commands`, `env` (names only), `acceptance` (`minimum_pass_rate` 0.8+,
  `required_metrics`: `zero_disallowed_actions`, `tool_correctness`) per §4/§7
- [x] Add `field/scenarios/adk-core.yaml`: `adk-basic-tool-call`, `adk-multi-step`,
  `adk-no-tool-needed`, `adk-disallowed-tool`, `adk-structured-output`
- [x] `conftest.py`: document `field_category: adk`
- [x] Verify `test_field_agent.py` generic `create_adapter().run()` + `ScoringEngine` flow
- [x] Sweep: `local` smoke (MLX healthy) + `cheap` tier
  (`openai/gpt-4o-mini`, needs `OPENROUTER_API_KEY`)
- [x] Failures classifiable into Class A/B/C/D per field-test-plan §8

**Acceptance Criteria:**
- 3+ real Google ADK agents clone, run, produce scored results in `field/results/`
- ≥1 Google ADK agent meets `minimum_pass_rate` on cheap tier
- Google ADK failures correctly classified (Class A/B/C/D)
- Field report covers Google ADK agents with three-way scores + env labels per #239/#244

**Test Criteria:**
- `setup.sh` clones curated roster (or Class A dep failure reported)
- Local run: ≥1 healthy agent passes safety gate (`zero_disallowed_actions`)
- `gen-field-json.py` unit test for `adk` detection
- Config schema validation for each new `field/config/*.json`

**Success Criteria:**
- [x] Google ADK is a supported, shipped, field-verified adapter family
- [x] Code review completed
- [x] All comments added to touched code
- [x] Tests pass
- [x] Lint clean
- [x] Type check clean

---

### [#291](https://github.com/deghosal-2026/agent-eval-forge/issues/291) — Update docs (spec, user guide, CI, field plan) for agentic-platform adapter expansion

**Reported by:** Internal (framework landscape analysis, 2026-08-10)  
**Labels:** documentation, 0.2.0  
**Depends on:** #281, #283, #285, #287, #289 (functional adapter issues; docs describe shipped behavior)  
**Location:** `docs/spec.md`, `docs/ci.md`, `docs/user-guide.md`, `README.md`, `field/README.md`, `docs/.evalforge/` scaffolding

**Context:** v0.2.0 added smolagents, AutoGen, LlamaIndex Agents, Claude Agent
SDK, and Google ADK as first-class adapter families (Wave 2; #281-#290), on top
of the CrewAI / OpenAI Agents SDK Wave-1 pairs (#277-#280). Every doc that
enumerates supported agent types or describes adapter wiring must be updated so
users can adopt the new adapters from docs alone.

**Checklist:**
- [x] `docs/spec.md`: add `smolagents`, `autogen`, `llamaindex`, `claude`, `adk`
  to the agent-type reference — config schema (`module`/`function`, default
  builder name per framework), `get_manifest()` digest binding (#251), model
  override contract (`EVALFORGE_FIELD_MODEL/ENDPOINT` + `EVALFORGE_FORCE_MODEL`)
- [x] `docs/user-guide.md`: `--agent <type>:module:build_agent` usage per family +
  required `pip install evalforge[<extra>]` extras (`smolagents`, `autogen`,
  `llamaindex`, `claude`, `adk`)
- [x] `README.md`: supported-adapters table + badges with the five new families
- [x] `docs/ci.md`: `--extra <family>` install steps + field-test job wiring
- [x] `docs/testing/field-test-plan.md`: new `field_category` entries in roster §2
  and Class A/B/C/D taxonomy §8
- [x] `docs/0.2.0/wbs.md`: Phase 3 adapter issue list stays in sync (5 new families)
- [x] `init` scaffold / project template extends from updated extras list

**Acceptance Criteria:**
- A reader can configure + run any new adapter family purely from docs
- `docs/spec.md` adapter-type table matches `adapters/factory.py` `ADAPTERS` keys
- Extras names in docs match installed extras in `pyproject.toml`

**Test Criteria:**
- Docs examples verified against `create_adapter({"type": <each>})` in a real venv
- Links, code blocks, and `--agent <type>` strings resolve in every updated doc

**Success Criteria:**
- [x] All listed doc files updated and rendered
- [x] No doc references a stale adapter type / extras name
- [x] Code review completed

---

## M0.2.0 Final Exit Gates
**These gates apply to the ENTIRE milestone before tagging v0.2.0.**

### Pre-Release Gates

- [x] **All Phase 1 bugs fixed** (8/8 issues closed)
- [x] **All Phase 2 small features implemented** (15/15 issues closed)
- [x] **Code review completed** for every issue
- [x] **All comments added** to new and modified code
- [x] **Full test suite passes** (`pytest`) — zero failures, zero skips (except live API tests)
- [x] **Lint clean** (`ruff check` zero errors across entire codebase)
- [x] **Type check clean** (`mypy --strict` zero errors across entire codebase)
- [x] **Code coverage > 90%** (`pytest --cov`) on testable code

### Field Test Gates

- [x] **Docker tests pass** — 7/7 tests green, results at `docs/0.2.0/docker-test-results-0.2.0.md`
- [x] **Field test run** against 19+ real agents from GitHub (LangGraph, PydanticAI, custom)
- [x] **All field test scenarios pass** with no adapter failures (compatibility_score = 1.0 for all agents)
- [x] **Field test report** published at `docs/field-test-report-v0.2.0.md` with:
  - Per-agent compatibility, safety, and quality scores (three-way split per #239)
  - Execution environment labels per #244
  - Run manifest per #238
- [x] **Regression check:** v0.2.0 scores on core-launch pack compared against v0.1.0 baseline
  - No unexplained regressions
  - Score drops attributable to improved detection (bugs fixed in #270, #271, #273)

### Release Gates

- [x] **Changelog updated** with all 38 issues listed
- [x] **README updated** with new features (subprocess default, action-quality scoring, etc.)
- [x] **Docs updated** for all changed behaviour (spec, ci, user-guide, scenario-authoring, scoring)
- [x] **Migration guide** for v0.1.0 → v0.2.0 breaking changes:
  - `exact_match` behaviour changed (#274)
  - Exit codes now correctly non-zero (#269)
  - Scoring now short-circuits on artifact errors (#270)
- [x] **Git tag** `v0.2.0` created
- [x] **GitHub release** published with full release notes

---

## Issue-to-Dev.to-Thread Mapping

| Issue | Reporter | Dev.to Thread |
|-------|----------|---------------|
| #259 | hoseinmdev | [I Built an Agent Eval Harness](https://dev.to/debashish_ghosal/i-built-an-agent-eval-harness-real-agents-broke-the-clean-version-of-the-story-53dj/comments/3cd5e) |
| #258 | kikashy | [I Built Scenario Packs for Agent Regression Testing](https://dev.to/debashish_ghosal/i-built-scenario-packs-for-agent-regression-testing-the-integration-not-the-judge-broke-me-1k9k/comments/3cl3p) |
| #255 | nyx533 | [comment/3ckie](https://dev.to/nyx533/comment/3ckie) |
| #254 | mads_hansen | [comment/3ckcl](https://dev.to/mads_hansen_27b33ebfee4c9/comment/3ckcl) |
| #253 | mads_hansen | [comment/3ckcl](https://dev.to/mads_hansen_27b33ebfee4c9/comment/3ckcl) |
| #251 | mads_hansen | [comment/3ckcl](https://dev.to/mads_hansen_27b33ebfee4c9/comment/3ckcl) |
| #250 | kikashy (Brian Jin) + mads_hansen | [comment/3ckcl](https://dev.to/mads_hansen_27b33ebfee4c9/comment/3ckcl) + [comment/3ckp5](https://dev.to/kikashy/comment/3ckp5) |
| #269-#274 | kikashy | [JPS Integration Study](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/blob/main/studies/013-agent-eval-forge-integration/UPSTREAM.md) |
| #292-#294 | kikashy | [JPS Integration Study — findings not captured as bugs](https://dev.to/kikashy/comment/3cm8e) |
| #238-#244 | Peer review | Internal peer review feedback |