"""Tests for evalforge.tools.cost_governor."""

from evalforge.tools.cost_governor import CostConfig, CostGovernor, CostStatus


class TestCostConfig:
    def test_defaults(self) -> None:
        c = CostConfig()
        assert c.max_total_cost_usd == 1.00
        assert c.max_per_scenario_cost_usd == 0.10
        assert c.max_total_tokens == 100_000
        assert c.abort_on_threshold is True
        assert c.warn_at_percent == 0.8

    def test_custom_values(self) -> None:
        c = CostConfig(
            max_total_cost_usd=5.0,
            max_per_scenario_cost_usd=0.5,
            max_total_tokens=200_000,
            abort_on_threshold=False,
            warn_at_percent=0.5,
        )
        assert c.max_total_cost_usd == 5.0
        assert c.max_per_scenario_cost_usd == 0.5
        assert c.max_total_tokens == 200_000
        assert c.abort_on_threshold is False
        assert c.warn_at_percent == 0.5


class TestCostStatus:
    def test_defaults(self) -> None:
        s = CostStatus()
        assert s.total_cost_usd == 0.0
        assert s.total_tokens == 0
        assert s.scenarios_run == 0
        assert s.scenarios_aborted == 0
        assert s.over_budget is False
        assert s.remaining_budget_usd == 0.0

    def test_custom_values(self) -> None:
        s = CostStatus(
            total_cost_usd=0.5,
            total_tokens=1000,
            scenarios_run=3,
            scenarios_aborted=1,
            over_budget=True,
            remaining_budget_usd=0.5,
        )
        assert s.total_cost_usd == 0.5
        assert s.total_tokens == 1000
        assert s.scenarios_run == 3
        assert s.scenarios_aborted == 1
        assert s.over_budget is True


class TestCostGovernorInit:
    def test_default_config(self) -> None:
        g = CostGovernor()
        assert g.status.total_cost_usd == 0.0
        assert g.status.remaining_budget_usd == 1.00

    def test_custom_config(self) -> None:
        cfg = CostConfig(max_total_cost_usd=10.0, max_total_tokens=500_000)
        g = CostGovernor(cfg)
        assert g.status.remaining_budget_usd == 10.0


class TestCanRunScenario:
    def test_within_budget(self) -> None:
        g = CostGovernor()
        assert g.can_run_scenario(0.05) is True

    def test_exceeds_per_scenario_limit(self) -> None:
        g = CostGovernor()
        assert g.can_run_scenario(0.20) is False

    def test_exceeds_remaining_budget(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.95, 500)
        assert g.can_run_scenario(0.06) is False

    def test_already_over_budget(self) -> None:
        g = CostGovernor()
        g.record_scenario(1.00, 100)
        assert g.can_run_scenario(0.01) is False

    def test_zero_estimated_cost_always_allowed_when_in_budget(self) -> None:
        g = CostGovernor()
        assert g.can_run_scenario(0.0) is True


class TestRecordScenario:
    def test_updates_status(self) -> None:
        g = CostGovernor()
        status = g.record_scenario(0.05, 500)
        assert status.total_cost_usd == 0.05
        assert status.total_tokens == 500
        assert status.scenarios_run == 1
        assert status.remaining_budget_usd == 0.95
        assert status.over_budget is False

    def test_over_cost_budget(self) -> None:
        g = CostGovernor()
        status = g.record_scenario(1.00, 0)
        assert status.over_budget is True
        assert status.total_cost_usd == 1.00

    def test_over_cost_budget_exceeds(self) -> None:
        g = CostGovernor()
        status = g.record_scenario(2.00, 0)
        assert status.over_budget is True

    def test_over_token_budget(self) -> None:
        g = CostGovernor()
        status = g.record_scenario(0.01, 100_000)
        assert status.over_budget is True

    def test_over_token_budget_exceeds(self) -> None:
        g = CostGovernor()
        status = g.record_scenario(0.01, 200_000)
        assert status.over_budget is True

    def test_multiple_scenarios(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.10, 100)
        g.record_scenario(0.10, 100)
        assert g.status.total_cost_usd == 0.20
        assert g.status.total_tokens == 200
        assert g.status.scenarios_run == 2
        assert g.status.remaining_budget_usd == 0.80

    def test_returns_status(self) -> None:
        g = CostGovernor()
        s = g.record_scenario(0.01, 10)
        assert s is g.status


class TestRecordAborted:
    def test_increments_counter(self) -> None:
        g = CostGovernor()
        assert g.status.scenarios_aborted == 0
        g.record_aborted()
        assert g.status.scenarios_aborted == 1
        g.record_aborted()
        assert g.status.scenarios_aborted == 2


class TestShouldWarn:
    def test_no_spend_no_warning(self) -> None:
        g = CostGovernor()
        assert g.should_warn() is False

    def test_below_threshold(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.50, 0)
        assert g.should_warn() is False

    def test_at_threshold(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.80, 0)
        assert g.should_warn() is True

    def test_above_threshold(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.90, 0)
        assert g.should_warn() is True

    def test_custom_warn_threshold(self) -> None:
        g = CostGovernor(CostConfig(warn_at_percent=0.5, max_total_cost_usd=10.0))
        g.record_scenario(6.0, 0)
        assert g.should_warn() is True


class TestRemainingScenariosEstimate:
    def test_typical_avg_cost(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.20, 100)
        assert g.remaining_scenarios_estimate(0.10) == 8

    def test_zero_remaining_budget(self) -> None:
        g = CostGovernor()
        g.record_scenario(1.00, 0)
        assert g.remaining_scenarios_estimate(0.10) == 0

    def test_negative_or_zero_avg_cost(self) -> None:
        g = CostGovernor()
        assert g.remaining_scenarios_estimate(0.0) == 999
        assert g.remaining_scenarios_estimate(-1.0) == 999

    def test_no_spend_yet(self) -> None:
        g = CostGovernor(CostConfig(max_total_cost_usd=10.0))
        assert g.remaining_scenarios_estimate(0.5) == 20

    def test_rounds_down(self) -> None:
        g = CostGovernor(CostConfig(max_total_cost_usd=1.0))
        g.record_scenario(0.25, 0)
        assert g.remaining_scenarios_estimate(0.10) == 7


class TestToDict:
    def test_initial_state(self) -> None:
        g = CostGovernor()
        d = g.to_dict()
        assert d["total_cost_usd"] == 0.0
        assert d["total_tokens"] == 0
        assert d["scenarios_run"] == 0
        assert d["scenarios_aborted"] == 0
        assert d["over_budget"] is False
        assert d["remaining_budget_usd"] == 1.0
        assert d["max_total_cost_usd"] == 1.0
        assert d["max_total_tokens"] == 100_000

    def test_after_recording(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.1234567, 500)
        g.record_aborted()
        d = g.to_dict()
        assert d["total_cost_usd"] == 0.123457
        assert d["total_tokens"] == 500
        assert d["scenarios_run"] == 1
        assert d["scenarios_aborted"] == 1


class TestReset:
    def test_resets_all_state(self) -> None:
        g = CostGovernor()
        g.record_scenario(0.50, 10000)
        g.record_aborted()
        g.record_aborted()
        g.reset()
        assert g.status.total_cost_usd == 0.0
        assert g.status.total_tokens == 0
        assert g.status.scenarios_run == 0
        assert g.status.scenarios_aborted == 0
        assert g.status.over_budget is False
        assert g.status.remaining_budget_usd == 1.00
