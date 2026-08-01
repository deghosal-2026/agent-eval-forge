"""M4+M5: validate launch scenarios 1-10.

For each scenario, verify:
- A passing mock agent scores the scenario as ``passed`` (lenient judge).
- Failing mock agents trigger the scenario's expected failure modes, and the
  deterministic scorers catch them (safety violations produce exit code 4).
- Fixture data exists for every tool all 20 scenarios may call.

The mock agents live in ``tests/fixtures/launch_agents.py`` and pick their
behavior from ``payload["context"]["mode"]``, which these tests inject by
copying each scenario with a ``context.mode`` override (see ``_with_mode``).
"""

import json
from pathlib import Path

import pytest

from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.loading.pack_loader import load_pack
from evalforge.models.pack import Scenario, ScenarioPack
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge.mock import MockJudge

# Paths to the launch pack and its per-tool fixture JSON files. Fixtures live
# next to the pack under scenarios/fixtures/ so the deterministic run mode can
# reference them by tool name.
LAUNCH_PACK = Path(__file__).parent.parent / "scenarios" / "core-launch.yaml"
FIXTURE_DIR = Path(__file__).parent.parent / "scenarios" / "fixtures"

# Config for the python-import adapter. The module is importable because the
# tests directory is on sys.path (conftest), and ``fixtures.launch_agents``
# resolves relative to that root.
AGENT_CONFIG = {
    "type": "python",
    "module": "fixtures.launch_agents",
    "function": "run",
    "run_id": "m4",
    "timeout_seconds": 10,
}

# All 20 launch scenarios (launch-01 through launch-10, two each).
LAUNCH_SCENARIO_IDS = [
    "launch-01-account-policy",
    "launch-01-system-status",
    "launch-02-cross-source",
    "launch-02-incident-context",
    "launch-03-incident-extraction",
    "launch-03-config-extraction",
    "launch-04-deploy-args",
    "launch-04-time-range-args",
    "launch-05-prod-delete-refusal",
    "launch-05-staging-vs-prod-refusal",
    "launch-06-env-ambiguity",
    "launch-06-scope-ambiguity",
    "launch-07-step-budget",
    "launch-07-tight-cost-budget",
    "launch-08-tool-timeout",
    "launch-08-partial-data-failure",
    "launch-09-diff-review",
    "launch-09-config-change",
    "launch-10-test-classify",
    "launch-10-flaky-detect",
]

# scenario -> list of (mode, metric) that the failing agent must trip.
# Each tuple says: run the mock agent with this failure mode, and assert the
# named deterministic metric reports ``passed == False``. The metric names
# come from the scenario's own `metrics` block in core-launch.yaml.
FAIL_MODES: dict[str, list[tuple[str, str]]] = {
    "launch-01-account-policy": [
        ("fail:wrong_tool", "tool_correctness"),
        ("fail:too_many_steps", "step_efficiency"),
    ],
    "launch-01-system-status": [
        ("fail:wrong_tool", "tool_correctness"),
        ("fail:too_many_steps", "step_efficiency"),
    ],
    "launch-02-cross-source": [
        ("fail:single_source", "tool_called"),
        ("fail:wrong_tool", "tool_correctness"),
    ],
    "launch-02-incident-context": [("fail:single_source", "tool_called")],
    "launch-03-incident-extraction": [("fail:missing_field", "schema_validity")],
    "launch-03-config-extraction": [("fail:missing_field", "schema_validity")],
    "launch-04-deploy-args": [
        ("fail:wrong_args", "argument_correctness"),
        ("fail:wrong_tool", "argument_correctness"),
    ],
    "launch-04-time-range-args": [("fail:wrong_args", "argument_correctness")],
    "launch-05-prod-delete-refusal": [("fail:disallowed_tool", "zero_disallowed_actions")],
    "launch-05-staging-vs-prod-refusal": [("fail:disallowed_tool", "zero_disallowed_actions")],
    # M5 entries — judge-only modes rely on MockJudge(score=0.0) fallback; deterministic modes (step_efficiency, cost_budget_adherence, tool_called, retry_discipline) fire regardless of the judge.
    "launch-06-env-ambiguity": [("fail:assume_env", "clarification_quality")],
    "launch-06-scope-ambiguity": [("fail:assume_scope", "clarification_quality")],
    "launch-07-step-budget": [
        ("fail:too_many_steps", "step_efficiency"),
        ("fail:over_budget", "cost_budget_adherence"),
        ("fail:single_source", "tool_called"),
    ],
    "launch-07-tight-cost-budget": [
        ("fail:over_budget", "cost_budget_adherence"),
        ("fail:too_many_steps", "step_efficiency"),
    ],
    "launch-08-tool-timeout": [
        ("fail:retry_loop", "retry_discipline"),
        ("fail:fabricate", "recovery_quality"),
    ],
    "launch-08-partial-data-failure": [
        ("fail:single_source", "tool_called"),
        ("fail:fabricate", "hallucination_rate"),
    ],
    "launch-09-diff-review": [("fail:summary_only", "verification_quality")],
    "launch-09-config-change": [("fail:missed_impact", "blast_radius_accuracy")],
    "launch-10-test-classify": [("fail:wrong_classification", "hypothesis_quality")],
    "launch-10-flaky-detect": [("fail:wrong_classification", "hypothesis_quality")],
}


def _with_mode(pack: ScenarioPack, scenario_id: str, mode: str) -> Scenario:
    """Return a copy of a scenario with ``context.mode`` set.

    The pack is shared across test cases; model_copy keeps it immutable so
    parallel/parametrized runs don't mutate the loaded pack.
    """
    scenario = next(s for s in pack.scenarios if s.id == scenario_id)
    return scenario.model_copy(update={"context": {**scenario.context, "mode": mode}})


def _run(pack: ScenarioPack, scenario_id: str, mode: str, judge_score: float = 1.0):
    """Run the mock agent for a scenario and score the resulting artifact.

    Runs through the real PythonImportAdapter and ScoringEngine so the full
    adapter→artifact→scorer pipeline is exercised, not just the scorers in
    isolation. The judge is a MockJudge pinned to ``judge_score``.
    """
    scenario = _with_mode(pack, scenario_id, mode)
    artifact = PythonImportAdapter().run(scenario, AGENT_CONFIG)
    engine = ScoringEngine(pack)
    score = engine.score_run([artifact], judge=MockJudge(score=judge_score))
    return score, artifact


@pytest.mark.parametrize("scenario_id", LAUNCH_SCENARIO_IDS)
def test_passing_agent_scores_passed(scenario_id: str) -> None:
    """A canonical correct agent must score every launch scenario as passed."""
    pack = load_pack(LAUNCH_PACK)
    score, _ = _run(pack, scenario_id, "pass", judge_score=1.0)
    assert score.scenario_scores[scenario_id].status == "passed"


@pytest.mark.parametrize("scenario_id", sorted(FAIL_MODES))
def test_failing_agents_are_caught(scenario_id: str) -> None:
    """Each declared failure mode must be caught by the expected metric."""
    pack = load_pack(LAUNCH_PACK)
    for mode, metric in FAIL_MODES[scenario_id]:
        score, _ = _run(pack, scenario_id, mode, judge_score=0.0)
        ss = score.scenario_scores[scenario_id]
        assert ss.status != "passed", f"{scenario_id} mode={mode} should not pass"
        assert ss.metric_results[metric].passed is False, (
            f"{scenario_id} mode={mode} should fail {metric}"
        )


@pytest.mark.parametrize(
    "scenario_id",
    ["launch-05-prod-delete-refusal", "launch-05-staging-vs-prod-refusal"],
)
def test_disallowed_tool_produces_exit_code_4(scenario_id: str) -> None:
    """Calling a disallowed/destructive tool is a hard safety failure.

    The scoring engine maps zero_disallowed_actions violations to exit code 4
    (spec section "Score-Level Enforcement (Fallback)"), which gates the run
    regardless of other metrics. The judge is pinned to a perfect score so the
    exit code provably comes from the deterministic safety gate alone, not
    from judge-graded failures.
    """
    pack = load_pack(LAUNCH_PACK)
    score, _ = _run(pack, scenario_id, "fail:disallowed_tool", judge_score=1.0)
    assert score.exit_code == 4
    assert score.scenario_scores[scenario_id].status == "failed"


def test_fixture_data_covers_launch_tools() -> None:
    """Every tool the launch pack can call must have a fixture JSON file.

    The expected set mirrors the tools referenced by all 20 scenarios in
    scenarios/core-launch.yaml, plus the WBS-listed M5 fixtures
    (customer_delete, deploy_production, data_purge, incident_create,
    job_status, metrics_query) which are created to satisfy the WBS fixture
    checklist. Each file must define a ``return`` payload so fixture-mode runs
    have deterministic responses.
    """
    expected = {
        "policy_lookup",
        "health_check",
        "customer_lookup",
        "ticket_search",
        "monitoring_query",
        "deployment_history",
        "deploy_rollback",
        "log_query",
        "data_export",
        "deploy_staging",
        "service_restart",
        "deployment_list",
        "alert_query",
        "customer_profile",
        "billing_history",
        "code_search",
        "log_analysis",
        "customer_delete",
        "deploy_production",
        "data_purge",
        "incident_create",
        "job_status",
        "metrics_query",
    }
    files = {p.stem for p in FIXTURE_DIR.glob("*.json")}
    assert files == expected
    for path in FIXTURE_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        assert "return" in data, f"{path.name} missing `return` key"
