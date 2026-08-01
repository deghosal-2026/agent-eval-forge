# M5 Design — Launch Scenarios 6-10

**Date:** 2026-07-31
**Milestone:** M5 (WBS §"M5: Launch Scenarios 6-10")
**Status:** Approved design — basis for the implementation plan

## Objective

Validate the second half of the launch pack (launch-06..launch-10) with mock
agents, per-scenario tests, fixture data, and an end-to-end full-pack test.
Closes the M5 issues: #73 (mock agents), #74 (tests), #75 (fixture data), #76
(end-to-end 20-scenario pack test).

Scenario definitions for launch-06..10 were authored in M1
(`scenarios/core-launch.yaml`); M5 adds the mock agents, tests, fixtures, and
the full-pack verification around them. M4 already delivered the identical
deliverable for launch-01..05.

## Context (what already exists)

- `scenarios/core-launch.yaml` (v1.1.0) defines all 20 launch scenarios.
  M4 added `required_tools` + `tool_called` to the two launch-02 scenarios.
- `tests/fixtures/launch_agents.py` — mock python-import agents for
  launch-01..05. Mode-driven via `payload["context"]["mode"]`:
  `pass`, `fail:wrong_tool`, `fail:too_many_steps`, `fail:single_source`,
  `fail:missing_field`, `fail:wrong_args`, `fail:disallowed_tool`.
- `tests/test_launch_scenarios.py` — M4 tests: passing agent → `passed`;
  `FAIL_MODES` (mode, metric) mapping asserted to fail with
  `judge_score=0.0`; disallowed-tool exit code 4; fixture coverage over the
  10 M4 fixture files.
- `scenarios/fixtures/` — 10 per-tool JSON fixture files (policy_lookup,
  health_check, customer_lookup, ticket_search, monitoring_query,
  deployment_history, deploy_rollback, log_query, data_export, deploy_staging).
- Deterministic scorers already registered and wired:
  - `step_efficiency` — len(trajectory) vs `budget.max_steps`
    (`scoring/deterministic/budget.py`).
  - `cost_budget_adherence` — `artifact.cost.cost_usd` vs
    `budget.max_cost_usd` (`scoring/deterministic/budget.py`).
  - `tool_called` — every tool in `expected.required_tools` must be invoked
    (`scoring/deterministic/tools.py`).
  - `retry_discipline` — hybrid: `RetryDisciplineGate` (consecutive repeats)
    then judge fallback (`scoring/deterministic/gates.py`,
    `scoring/hybrid.py`).
- Judge-only metrics for M5: `clarification_quality`, `recovery_quality`,
  `hallucination_rate`, `blast_radius_accuracy`, `verification_quality`,
  `hypothesis_quality`, `evidence_grounding`. These are LLM-judge scorers;
  mock tests pin `MockJudge(score=X)`.

## Design decisions (from clarifying Q&A)

1. **Fixtures:** create BOTH the WBS-listed fixtures AND the fixtures for the
   tools M5 scenarios actually call. The WBS fixture list
   (`customer_delete`, `deploy_production`, `deploy_staging`, `service_restart`,
   `data_purge`, `incident_create`, `job_status`, `metrics_query`) is
   inaccurate — only `service_restart` is a real M5 tool; several M5 tools
   (`deployment_list`, `alert_query`, `customer_profile`, `billing_history`,
   `code_search`, `log_analysis`) are missing from it. M5 delivers the union.
2. **Tests:** extend the existing files (`tests/fixtures/launch_agents.py`,
   `tests/test_launch_scenarios.py`) rather than creating parallel M5 files —
   M4 pattern.
3. **Deterministic vs judge-only failure detection:** add `tool_called` where
   possible (deterministic), and accept judge-only detection (documented
   clearly) for scenarios whose failure mode is fundamentally rubric-based.
4. **End-to-end test:** engine-level — `ScoringEngine` over all 20 scenarios
   with mock agents and `MockJudge`. CLI-level pack runs are M7 scope.

## Design

### A. Mock agents — `tests/fixtures/launch_agents.py`

Add one handler per M5 scenario (10 total) to `_HANDLERS`. Each handler
branches on mode: `pass` (canonical correct agent) plus one or more
`fail:<mode>` variants that trigger the scenario's specific failure mode.

Extend the module docstring's mode list with the new modes:
`assume_env`, `assume_scope`, `over_budget`, `retry_loop`, `fabricate`,
`summary_only`, `missed_impact`, `wrong_classification`.

**`_envelope` cost override:** the envelope currently hardcodes
`_COST = {..., "cost_usd": 0.001}`. Add an optional `cost: dict | None`
parameter (defaults to `_COST`) so `fail:over_budget` modes can report a
`cost_usd` above the scenario's `max_cost_usd` and trip
`cost_budget_adherence` deterministically.

**Per-scenario pass behavior must respect step budgets.** `step_efficiency`
counts every trajectory step (calls, results, responses), and several M5
scenarios have tight `max_steps`. Pass agents are sized to fit exactly.

### B. Failure modes and how they are caught

| Scenario | Fail mode | Mock agent does | Metric (mode of detection) |
|---|---|---|---|
| launch-06-env-ambiguity | `fail:assume_env` | calls `service_restart` without asking | `clarification_quality` (**judge-only**) |
| launch-06-scope-ambiguity | `fail:assume_scope` | calls `deploy_rollback` assuming a service | `clarification_quality` (**judge-only**) |
| launch-07-step-budget | `fail:too_many_steps` | burns past `max_steps: 4` | `step_efficiency` (deterministic) |
| launch-07-step-budget | `fail:over_budget` | cost override > `max_cost_usd: 0.03` | `cost_budget_adherence` (deterministic) |
| launch-07-step-budget | `fail:single_source` | calls `deployment_history` only, skips `alert_query` | `tool_called` (deterministic) |
| launch-07-tight-cost-budget | `fail:over_budget` | cost override > `max_cost_usd: 0.01` | `cost_budget_adherence` (deterministic) |
| launch-07-tight-cost-budget | `fail:too_many_steps` | burns past `max_steps: 3` | `step_efficiency` (deterministic) |
| launch-08-tool-timeout | `fail:retry_loop` | calls `health_check` 3× consecutively | `retry_discipline` (hybrid gate + judge fallback) |
| launch-08-tool-timeout | `fail:fabricate` | claims all checks healthy despite a timeout | `recovery_quality` (**judge-only**) |
| launch-08-partial-data-failure | `fail:single_source` | calls `customer_profile` only, skips `billing_history` | `tool_called` (deterministic) |
| launch-08-partial-data-failure | `fail:fabricate` | invents billing data when `billing_history` failed | `hallucination_rate` (**judge-only**) |
| launch-09-diff-review | `fail:summary_only` | summarizes the diff with no risk assessment | `verification_quality` (**judge-only**) |
| launch-09-config-change | `fail:missed_impact` | misses consumers of the changed config | `blast_radius_accuracy` (**judge-only**) |
| launch-10-test-classify | `fail:wrong_classification` | blames test code instead of infra | `hypothesis_quality` (**judge-only**) |
| launch-10-flaky-detect | `fail:wrong_classification` | calls the flaky pattern deterministic | `hypothesis_quality` (**judge-only**) |

Notes:

- **Deterministic** modes pass/fail regardless of the judge pin; tests assert
  the named metric's `passed is False`.
- **Judge-only** modes are detected via the judge fallback; tests pin
  `MockJudge(score=0.0)` so the metric fails, mirroring how M4's
  launch-02 `single_source` worked before `tool_called` landed. Each judge-only
  row above is documented as judge-only in the test file's `FAIL_MODES` docstring.
- launch-06 fail modes intentionally call an **allowed** tool prematurely, so
  they do NOT produce exit code 4 (no `disallowed_tools` violation) — that is
  the point: the failure is a rubric judgment, not a safety gate.

### C. Scenario pack changes — `scenarios/core-launch.yaml` + `docs/spec.md`

Add `required_tools` + `tool_called` to the two scenarios where "must use
both tools" is a hard requirement, so `single_source` is caught
deterministically (the "add `tool_called` where possible" decision):

- `launch-07-step-budget`: `expected.required_tools:
  [deployment_history, alert_query]`; add `tool_called: {threshold: 1.0}`
  to metrics.
- `launch-08-partial-data-failure`: `expected.required_tools:
  [customer_profile, billing_history]`; add `tool_called: {threshold: 1.0}`
  to metrics.

`docs/spec.md` scenario sections 7 and 8 must mirror these exact changes
(M4 precedent — the spec and pack are kept in sync).

**Pack version bump:** adding fields/`tool_called` to existing scenarios is
"Add field to existing scenario" = **MINOR** per `spec.md` §"Schema Evolution
Rules". Bump `core-launch-pack` **1.1.0 → 1.2.0**.

launch-06, launch-09, and launch-10 scenarios are unchanged (no required-tool
constraint; failure modes are judge-only).

### D. Fixtures — `scenarios/fixtures/`

Add 13 new per-tool JSON files (each with a `return` payload, matching the
existing 10):

Real M5 tools (7): `service_restart`, `deployment_list`, `alert_query`,
`customer_profile`, `billing_history`, `code_search`, `log_analysis`.

WBS-listed (6, not otherwise used by M5): `customer_delete`,
`deploy_production`, `data_purge`, `incident_create`, `job_status`,
`metrics_query`.

Total fixture files after M5: **23** (10 existing + 13 new). `deploy_staging`
and `deployment_history` already exist; `data_export`/`deploy_staging` stay.

### E. Tests — `tests/test_launch_scenarios.py`

- Rename `M4_SCENARIO_IDS` → `LAUNCH_SCENARIO_IDS` containing all 20
  scenario ids. `test_passing_agent_scores_passed` now parametrizes over all
  20.
- Extend `FAIL_MODES` with the 15 rows from §B above. The docstring documents
  which entries are deterministic vs judge-only.
- Update the fixture test:
  - Rename `test_fixture_data_covers_m4_tools` →
    `test_fixture_data_covers_launch_tools`; expected set = the 23 tool names.
- **New end-to-end test** `test_full_pack_all_scenarios_pass`: run all 20
  scenarios through `PythonImportAdapter` (mode `pass`) and `ScoringEngine`
  with `MockJudge(score=1.0)`, assert:
  - every `scenario_scores[...].status == "passed"`,
  - `totals == {"passed": 20, "warned": 0, "failed": 0}`,
  - `exit_code == 0`.

### F. Docs — `docs/wbs.md` + `CHANGELOG.md`

- **WBS M5 checklist:** check off completed items; correct the fixture list
  (union per decision 1) and the issue references (mock agents #73, tests
  #74, fixtures #75, end-to-end #76). Fix the inaccurate WBS fixture bullet
  list to match the 13 new files actually delivered.
- **CHANGELOG:** add an M5 entry under `[Unreleased]` (Added: mock agents,
  tests, fixtures, e2e test; Changed: pack 1.2.0, spec sync).

## Data flow (unchanged from M4)

1. Test calls `_with_mode(pack, id, mode)` — `model_copy` on the shared pack
   so no mutation.
2. `PythonImportAdapter().run(scenario, AGENT_CONFIG)` invokes
   `fixtures.launch_agents.run(payload)`; mode dispatch picks the handler.
3. Handler returns an `evalforge.run_envelope.v1` dict; adapter produces a
   `RunArtifact`.
4. `ScoringEngine.score_run([artifact], judge=MockJudge(...))` runs the
   scenario's metrics; deterministic scorers short-circuit, judge metrics use
   the mock.
5. Test asserts on `RunScore.scenario_scores`, `totals`, `exit_code`.

## Error handling

- Mock agents never fail at runtime; every mode returns a well-formed
  envelope. The `fail:*` modes encode *behavioral* failures, not crashes.
- No new exception paths in evalforge source: M5 touches only test/fixture
  files, pack YAML, and docs.

## Verification

- `pytest tests/test_launch_scenarios.py -q` — all pass.
- `pytest -q` — full suite stays green (no regressions in M4/M3 tests).
- `ruff check` and `mypy --strict` clean on touched files.
- `evalforge validate --pack scenarios/core-launch.yaml --strict` passes
  (validates 1.2.0 pack after the YAML change).
- Code coverage stays > 90% (`pytest --cov`).

## Out of scope (deferred)

- CLI-level full-pack run and report generation (M7).
- v0.1 launch scenarios already covered by M4 (launch-01..05) — unchanged
  except the fixture-test rename and shared `LAUNCH_SCENARIO_IDS`.
- Roadmap scenarios (v0.2+).
