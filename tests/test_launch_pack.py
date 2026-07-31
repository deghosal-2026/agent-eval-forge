from pathlib import Path

from evalforge.loading.pack_loader import load_pack

LAUNCH_PACK = Path(__file__).parent.parent / "scenarios" / "core-launch.yaml"

EXPECTED_IDS = {
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
}


def test_launch_pack_loads() -> None:
    pack = load_pack(LAUNCH_PACK)
    assert pack.pack.name == "core-launch-pack"
    ids = {s.id for s in pack.scenarios}
    assert ids == EXPECTED_IDS


def test_launch_pack_scenarios_have_required_fields() -> None:
    pack = load_pack(LAUNCH_PACK)
    for scenario in pack.scenarios:
        assert scenario.input
        assert scenario.title
        assert scenario.metrics
        assert scenario.budget is not None
