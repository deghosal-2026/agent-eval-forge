from __future__ import annotations

from evalforge.tools.advanced import (
    ABGate,
    BudgetOptimizer,
    ComplianceHooks,
    DataLakeExporter,
    DistributedExecutor,
    FlakinessProfiler,
    GitHubPRGate,
    GovernancePolicy,
    HTMLReportEnhancer,
    LeaderboardEntry,
    LeaderboardIntegration,
    ModelMatrixRunner,
    MultiAgentEvaluator,
    PackSigner,
    StressTester,
    TelemetryExporter,
    TutorialRegistry,
    VSCodeIntegration,
)
from evalforge.tools.cost_governor import CostConfig, CostGovernor
from evalforge.tools.fuzzer import ScenarioFuzzer
from evalforge.tools.linter import ScenarioLinter
from evalforge.tools.secrets_scanner import SecretsScanner
from evalforge.tools.shrinker import ReproMinimizer


class TestTools:
    def test_linter_detects_untagged(self) -> None:
        from evalforge.models.pack import PackMetadata, Scenario, ScenarioPack
        pack = ScenarioPack(
            pack=PackMetadata(name="test", version="1.0"),
            scenarios=[Scenario(id="s1", title="t1", input="hi", allowed_tools=[], metrics={})],
        )
        report = ScenarioLinter.lint(pack)
        assert any(i.rule == "untagged" for i in report.issues)

    def test_fuzzer_produces_variants(self) -> None:
        from evalforge.models.pack import PackMetadata, Scenario, ScenarioPack
        pack = ScenarioPack(
            pack=PackMetadata(name="test", version="1.0"),
            scenarios=[Scenario(id="s1", title="t1", input="hello", allowed_tools=[], metrics={})],
        )
        fuzzed = ScenarioFuzzer().fuzz_pack(pack)
        assert len(fuzzed.scenarios) > 0

    def test_cost_governor_stops_at_limit(self) -> None:
        gov = CostGovernor(CostConfig(max_total_cost_usd=0.50, max_per_scenario_cost_usd=0.20))
        assert gov.can_run_scenario(0.10)
        gov.record_scenario(0.30, 100)
        gov.record_scenario(0.25, 100)
        assert gov.status.total_cost_usd == 0.55
        assert gov.status.over_budget

    def test_secrets_scanner_detects_api_key(self) -> None:
        issues = SecretsScanner.scan_text("My key is sk-abc123def456ghi789jkl012", "test")
        assert len(issues) > 0
        assert any("api_key" == i.issue_type for i in issues)

    def test_secrets_scanner_clean_text(self) -> None:
        issues = SecretsScanner.scan_text("The answer is 42.", "test")
        assert len(issues) == 0

    def test_repro_minimizer_half_input(self) -> None:
        minimizer = ReproMinimizer()
        result = minimizer.minimize(
            {"input": "hello world test scenario", "allowed_tools": [], "id": "t1"},
            lambda d: len(d.get("input", "")) > 5,
        )
        assert result.iterations >= 1
        assert len(result.minimized_input) <= len(result.original_input)

    def test_stress_tester_percentiles(self) -> None:
        result = StressTester.analyze_durations([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
        assert result.p50_ms == 600  # nearest-rank (index n//2)
        assert result.p95_ms >= 950

    def test_model_matrix_aggregate(self) -> None:
        runner = ModelMatrixRunner()
        runner.add_result("openai", "gpt-4o", 0.9, 0.05, 2000)
        runner.add_result("openai", "gpt-4o", 0.85, 0.04, 1800)
        runner.add_result("anthropic", "claude", 0.95, 0.06, 2500)
        agg = runner.aggregate()
        assert len(agg) == 2
        best = runner.best_by_score()
        assert best is not None
        assert best.provider == "anthropic"

    def test_flakiness_profiler(self) -> None:
        result = FlakinessProfiler.analyze("s1", [1.0, 1.0, 1.0, 1.0])
        assert not result.is_flaky

    def test_ab_gate_recommends_candidate(self) -> None:
        result = ABGate.compare([0.5, 0.5, 0.5], [0.9, 0.9, 0.9])
        assert "ship candidate" in result.recommendation

    def test_compliance_hooks_record(self) -> None:
        hooks = ComplianceHooks()
        hooks.record_check("ACCESS_CONTROL", {"test": True}, True)
        assert hooks.is_compliant()

    def test_html_enhancer_diff(self) -> None:
        diff = HTMLReportEnhancer.diff_view({"a": 1}, {"a": 2})
        assert "<td>a</td>" in diff
        assert "<td>1</td>" in diff
        assert "<td>2</td>" in diff

    def test_datalake_jsonl(self) -> None:
        result = DataLakeExporter.to_jsonl([{"a": 1}, {"a": 2}])
        assert result.count("\n") == 1

    def test_leaderboard_top_n(self) -> None:
        lb = LeaderboardIntegration()
        lb.submit(LeaderboardEntry("agent1", 0.9, 10, 10, ""))
        lb.submit(LeaderboardEntry("agent2", 0.7, 7, 10, ""))
        top = lb.top_n(1)
        assert top[0].agent_name == "agent1"

    def test_pack_signer(self) -> None:
        signed = PackSigner.sign({"name": "test"})
        assert "signature" in signed

    def test_tutorial_registry(self) -> None:
        reg = TutorialRegistry()
        assert len(reg.all()) == 3
        assert len(reg.list_by_tag("beginner")) == 1

    def test_vscode_generates_tasks(self) -> None:
        tasks = VSCodeIntegration.generate_tasks_json()
        assert "evalforge: run scenarios" in tasks

    def test_github_pr_gate(self) -> None:
        payload = GitHubPRGate.generate_check_payload("success", "All passed", {"score": 1.0})
        assert payload["conclusion"] == "success"

    def test_distributed_executor(self) -> None:
        executor = DistributedExecutor()
        executor.submit("j1", {"input": "test"})
        assert executor.pending() == 1
        result = executor.process_one(lambda s: {"output": s["input"]})
        assert result == {"output": "test"}
        assert executor.pending() == 0

    def test_telemetry_prometheus(self) -> None:
        output = TelemetryExporter.to_prometheus_metrics({"scenarios.passed": 10.0})
        assert "evalforge_scenarios_passed" in output

    def test_governance_rbac(self) -> None:
        assert GovernancePolicy.can("admin", "admin")
        assert not GovernancePolicy.can("viewer", "admin")
        assert GovernancePolicy.can("developer", "run")

    def test_budget_optimizer(self) -> None:
        results = [
            {"passed": True, "steps": 2, "cost_usd": 0.005},
            {"passed": True, "steps": 5, "cost_usd": 0.02},
        ]
        profile = BudgetOptimizer.find_minimal_budget(results, 0.8)
        assert profile.name in ("minimal", "moderate", "generous", "unbounded")

    def test_multi_agent_evaluator(self) -> None:
        result = MultiAgentEvaluator.evaluate([
            {"agent": "planner", "type": "response"},
            {"agent": "worker", "type": "handoff"},
        ])
        assert result["agents_involved"] == 2
        assert result["handoffs"] == 1
