# Launch Scenarios — Design

Covers the launch pack failure modes, mock agent architecture, fixture strategy, and end-to-end testing approach.

Covers launch scenarios 1-10 (M4 delivered 1-5, M5 delivered 6-10).

## Objective

Validate the launch pack (launch-01..launch-10) with mock agents, per-scenario
tests, fixture data, and an end-to-end full-pack test.

Scenario definitions were authored in M1 (`scenarios/core-launch.yaml`). M4/M5
add the mock agents, tests, fixtures, and full-pack verification.

## Context (what exists)

- `scenarios/core-launch.yaml` defines all 20 launch scenarios.
- `tests/fixtures/launch_agents.py` — mock python-import agents, mode-driven via
  `payload["context"]["mode"]`: `pass`, `fail:wrong_tool`, `fail:too_many_steps`,
  `fail:single_source`, `fail:missing_field`, `fail:wrong_args`,
  `fail:disallowed_tool`, `assume_env`, `assume_scope`, `over_budget`,
  `retry_loop`, `fabricate`, `summary_only`, `missed_impact`, `wrong_classification`.
- `tests/test_launch_scenarios.py` — passing agent → `passed`; `FAIL_MODES`
  (mode, metric) mapping asserted to fail; disallowed-tool exit code 4;
  fixture coverage tests.
- `scenarios/fixtures/` — per-tool JSON fixture files.
- Deterministic scorers already registered and wired:
  - `step_efficiency`, `cost_budget_adherence`, `tool_called`, `retry_discipline`.
- Judge-only metrics: `clarification_quality`, `recovery_quality`,
  `hallucination_rate`, `blast_radius_accuracy`, `verification_quality`,
  `hypothesis_quality`, `evidence_grounding`. These are LLM-judge scorers;
  mock tests pin `MockJudge(score=X)`.

## Design Decisions

1. **Fixtures:** create both the WBS-listed fixtures and the fixtures for the
   tools scenarios actually call.
2. **Tests:** extend existing files (`tests/fixtures/launch_agents.py`,
   `tests/test_launch_scenarios.py`) rather than creating parallel files.
3. **Deterministic vs judge-only failure detection:** add `tool_called` where
   possible (deterministic), and accept judge-only detection (documented
   clearly) for scenarios whose failure mode is fundamentally rubric-based.
4. **End-to-end test:** engine-level — `ScoringEngine` over all 20 scenarios
   with mock agents and `MockJudge`. CLI-level pack runs are M7 scope.

## Failure Modes

### Scenarios 1-5 (M4)

| Scenario | Fail mode | Mock agent does | Metric |
|---|---|---|---|
| launch-01-account-policy | `fail:wrong_tool` | calls `health_check` instead of `policy_lookup` | `tool_correctness` |
| launch-02-multi-source | `fail:single_source` | calls 1 tool only when 2 required | `tool_called` |
| launch-03-extract-json | `fail:missing_field` | omits a required field | `field_correctness` |
| launch-04-deploy-args | `fail:wrong_args` | wrong tool arguments | `argument_correctness` |
| launch-05-read-only | `fail:disallowed_tool` | calls a disallowed tool | `zero_disallowed_actions` (exit 4) |

### Scenarios 6-10 (M5)

| Scenario | Fail mode | Mock agent does | Metric |
|---|---|---|---|
| launch-06-env-ambiguity | `fail:assume_env` | calls `service_restart` without asking | `clarification_quality` (judge-only) |
| launch-06-scope-ambiguity | `fail:assume_scope` | calls `deploy_rollback` assuming a service | `clarification_quality` (judge-only) |
| launch-07-step-budget | `fail:too_many_steps` | burns past `max_steps: 4` | `step_efficiency` (deterministic) |
| launch-07-step-budget | `fail:over_budget` | cost override > `max_cost_usd: 0.03` | `cost_budget_adherence` (deterministic) |
| launch-07-step-budget | `fail:single_source` | calls `deployment_history` only, skips `alert_query` | `tool_called` (deterministic) |
| launch-07-tight-cost-budget | `fail:over_budget` | cost override > `max_cost_usd: 0.01` | `cost_budget_adherence` (deterministic) |
| launch-07-tight-cost-budget | `fail:too_many_steps` | burns past `max_steps: 3` | `step_efficiency` (deterministic) |
| launch-08-tool-timeout | `fail:retry_loop` | calls `health_check` 3x consecutively | `retry_discipline` (hybrid) |
| launch-08-tool-timeout | `fail:fabricate` | claims all checks healthy despite a timeout | `recovery_quality` (judge-only) |
| launch-08-partial-data-failure | `fail:single_source` | calls `customer_profile` only, skips `billing_history` | `tool_called` (deterministic) |
| launch-08-partial-data-failure | `fail:fabricate` | invents billing data when `billing_history` failed | `hallucination_rate` (judge-only) |
| launch-09-diff-review | `fail:summary_only` | summarizes the diff with no risk assessment | `verification_quality` (judge-only) |
| launch-09-config-change | `fail:missed_impact` | misses consumers of the changed config | `blast_radius_accuracy` (judge-only) |
| launch-10-test-classify | `fail:wrong_classification` | blames test code instead of infra | `hypothesis_quality` (judge-only) |
| launch-10-flaky-detect | `fail:wrong_classification` | calls the flaky pattern deterministic | `hypothesis_quality` (judge-only) |

Notes:
- **Deterministic** modes pass/fail regardless of the judge pin; tests assert
  the named metric's `passed is False`.
- **Judge-only** modes are detected via the judge fallback; tests pin
  `MockJudge(score=0.0)` so the metric fails.
- launch-06 fail modes intentionally call an **allowed** tool prematurely, so
  they do NOT produce exit code 4 — the failure is a rubric judgment, not a
  safety gate.

## Data flow

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

## Verification

- `pytest tests/test_launch_scenarios.py -q` — all pass.
- `pytest -q` — full suite stays green.
- `ruff check` and `mypy --strict` clean.
- `evalforge validate --pack scenarios/core-launch.yaml --strict` passes.
- Code coverage stays > 90% (`pytest --cov`).