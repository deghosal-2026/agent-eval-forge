"""Targeted coverage tests for uncovered lines in evalforge.tools.advanced."""

from __future__ import annotations

import pytest

from evalforge.tools.advanced import (
    ABGate,
    ApprovalWorkflow,
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
    PromptVersion,
    PromptVersionManager,
    StressTester,
    TelemetryExporter,
    ToolApprovalEvaluator,
    TutorialRegistry,
    VSCodeIntegration,
)

# --- L78: MultiAgentEvaluator.evaluate with errors ---

def test_multi_agent_evaluator_with_errors() -> None:
    result = MultiAgentEvaluator.evaluate([
        {"agent": "planner", "type": "response", "error": "timeout"},
        {"agent": "worker", "type": "handoff"},
    ])
    assert result["errors"] == 1
    assert result["error_details"] == ["planner: timeout"]
    assert result["passed"] is False


# --- L126-143: ToolApprovalEvaluator.check_approval ---

def test_approval_workflow_no_approval_violation() -> None:
    wf = ApprovalWorkflow("deploy", requires_approval=True, approver_role="human")
    result = ToolApprovalEvaluator.check_approval(
        [{"tool": "deploy", "approved": False}], wf,
    )
    assert result["violations"] == ["Tool deploy called without approval"]
    assert result["passed"] is False


def test_approval_workflow_auto_approval_counting() -> None:
    wf = ApprovalWorkflow("deploy", requires_approval=True, approver_role="human", max_auto_approvals=2)  # noqa: E501
    result = ToolApprovalEvaluator.check_approval(
        [
            {"tool": "deploy", "approved": True, "approved_by": "ai"},
            {"tool": "deploy", "approved": True, "approved_by": "ai"},
        ],
        wf,
    )
    assert result["auto_approvals_used"] == 2
    assert result["passed"] is True


def test_approval_workflow_auto_approval_exceeded() -> None:
    wf = ApprovalWorkflow("deploy", requires_approval=True, approver_role="human", max_auto_approvals=1)  # noqa: E501
    result = ToolApprovalEvaluator.check_approval(
        [
            {"tool": "deploy", "approved": True, "approved_by": "ai"},
            {"tool": "deploy", "approved": True, "approved_by": "ai"},
            {"tool": "deploy", "approved": True, "approved_by": "ai"},
        ],
        wf,
    )
    assert result["auto_approvals_used"] == 1
    assert len(result["violations"]) == 2
    assert "exceeded auto-approval limit" in result["violations"][0]
    assert result["passed"] is False


def test_approval_workflow_no_approval_required() -> None:
    wf = ApprovalWorkflow("read", requires_approval=False)
    result = ToolApprovalEvaluator.check_approval(
        [{"tool": "read", "approved": False}], wf,
    )
    assert result["passed"] is True
    assert result["violations"] == []


def test_approval_workflow_skips_other_tools() -> None:
    wf = ApprovalWorkflow("deploy", requires_approval=True)
    result = ToolApprovalEvaluator.check_approval(
        [{"tool": "read", "approved": False}], wf,
    )
    assert result["passed"] is True
    assert result["violations"] == []


def test_approval_workflow_human_approver() -> None:
    wf = ApprovalWorkflow("deploy", requires_approval=True, approver_role="human")
    result = ToolApprovalEvaluator.check_approval(
        [{"tool": "deploy", "approved": True, "approved_by": "human"}], wf,
    )
    assert result["passed"] is True
    assert result["auto_approvals_used"] == 0


# --- L196: StressTester.analyze_durations empty ---

def test_stress_tester_empty() -> None:
    result = StressTester.analyze_durations([])
    assert result.scenarios == 0
    assert result.total_duration_ms == 0
    assert result.passed is True


# --- L270: BudgetOptimizer fallback to unbounded ---

def test_budget_optimizer_fallback_unbounded() -> None:
    results = [
        {"passed": False, "steps": 99, "cost_usd": 0.99},
    ]
    profile = BudgetOptimizer.find_minimal_budget(results, 0.8)
    assert profile.name == "unbounded"


# --- L349, L358-361: ModelMatrixRunner.best_by_score/best_by_cost empty ---

def test_model_matrix_best_empty() -> None:
    runner = ModelMatrixRunner()
    assert runner.best_by_score() is None
    assert runner.best_by_cost() is None


# --- L404, L412, L423, L436-445: PromptVersionManager ---

def test_prompt_version_manager_save_and_get() -> None:
    mgr = PromptVersionManager()
    pv = PromptVersion("1.0", "Hello {name}", {"name": "default"}, "2024-01-01T00:00:00Z")
    mgr.save_version(pv)
    assert mgr.get_version("1.0") is pv
    assert mgr.get_version("2.0") is None


def test_prompt_version_manager_diff_with_registered_versions() -> None:
    mgr = PromptVersionManager()
    mgr.save_version(PromptVersion("1.0", "line1\nline2\nline3", {"x": "1"}, "2024-01-01T00:00:00Z"))  # noqa: E501
    mgr.save_version(PromptVersion("2.0", "line1\nline2\nline4", {"y": "2"}, "2024-02-01T00:00:00Z"))  # noqa: E501
    diff = mgr.diff("1.0", "2.0")
    assert diff.v1 == "1.0"
    assert diff.v2 == "2.0"
    assert "line4" in diff.added_lines
    assert "line3" in diff.removed_lines
    assert set(diff.changed_variables) == {"x", "y"}


def test_prompt_version_manager_diff_raw_strings() -> None:
    mgr = PromptVersionManager()
    diff = mgr.diff("lineA\nlineB", "lineA\nlineC")
    assert diff.added_lines == ["lineC"]
    assert diff.removed_lines == ["lineB"]
    assert diff.changed_variables == []


def test_prompt_version_manager_diff_mixed() -> None:
    mgr = PromptVersionManager()
    mgr.save_version(PromptVersion("1.0", "hello world", {"a": "1"}, "2024-01-01T00:00:00Z"))
    diff = mgr.diff("1.0", "hello mars")
    assert diff.added_lines == ["hello mars"]
    assert diff.removed_lines == ["hello world"]
    assert diff.changed_variables == ["a"]


# --- L505: ComplianceHooks.export_report ---

def test_compliance_hooks_export_report() -> None:
    hooks = ComplianceHooks()
    hooks.record_check("ACCESS_CONTROL", {"test": True}, True)
    hooks.record_check("DATA_INTEGRITY", {"hash": "abc"}, False)
    report = hooks.export_report()
    assert len(report) == 2
    assert report[0]["control"] == "ACCESS_CONTROL"
    assert report[0]["passed"] is True
    assert report[1]["control"] == "DATA_INTEGRITY"
    assert report[1]["passed"] is False
    assert hooks.is_compliant() is False


# --- L527: HTMLReportEnhancer.scenario_deep_link with base_url ---

def test_html_report_scenario_deep_link_with_base() -> None:
    link = HTMLReportEnhancer.scenario_deep_link("s42", base_url="https://example.com")
    assert link == "https://example.com#scenario-s42"


# --- L548: HTMLReportEnhancer.diff_view no changes ---

def test_html_report_diff_view_no_changes() -> None:
    diff = HTMLReportEnhancer.diff_view({"a": 1}, {"a": 1})
    assert diff == "<p>No changes.</p>"


# --- L582-587: DataLakeExporter.to_csv non-empty ---

def test_datalake_to_csv_with_results() -> None:
    result = DataLakeExporter.to_csv([
        {"name": "Alice", "score": "0.9"},
        {"name": "Bob", "score": "0.8"},
    ])
    lines = result.split("\n")
    assert lines[0] == "name,score"
    assert "Alice" in result
    assert "Bob" in result


def test_datalake_to_csv_empty() -> None:
    assert DataLakeExporter.to_csv([]) == ""


# --- L641: LeaderboardIntegration.to_json ---

def test_leaderboard_to_json() -> None:
    lb = LeaderboardIntegration()
    lb.submit(LeaderboardEntry("agentA", 0.95, 10, 10, "2024-01-01T00:00:00Z"))
    lb.submit(LeaderboardEntry("agentB", 0.80, 8, 10, "2024-01-02T00:00:00Z"))
    json_str = lb.to_json()
    assert '"agent"' in json_str
    assert '"score"' in json_str
    assert "agentA" in json_str
    import json
    data = json.loads(json_str)
    assert data[0]["agent"] == "agentA"
    assert data[0]["score"] == 0.95


# --- L681: PackSigner.verify ---

def test_pack_signer_verify() -> None:
    signed = PackSigner.sign({"name": "test"})
    assert PackSigner.verify(signed) is False
    assert PackSigner.verify({"signature": {"verified": True}}) is True
    assert PackSigner.verify({}) is False


# --- L844: FlakinessProfiler.analyze single score (< 2) ---

def test_flakiness_profiler_single_score() -> None:
    result = FlakinessProfiler.analyze("s1", [0.5])
    assert result.total_runs == 1
    assert result.flake_rate == 0.0
    assert result.score_variance == 0.0
    assert result.is_flaky is False


# --- L898: ABGate.compare empty ---

def test_ab_gate_compare_empty() -> None:
    result = ABGate.compare([], [])
    assert result.improvement == 0
    assert result.confidence == "low"
    assert result.recommendation == "insufficient data"


def test_ab_gate_compare_one_empty() -> None:
    result = ABGate.compare([0.5], [])
    assert result.recommendation == "insufficient data"


# --- L904: ABGate.compare confidence high (>=10 each) ---

def test_ab_gate_compare_high_confidence() -> None:
    baseline = [0.5] * 10
    candidate = [0.7] * 10
    result = ABGate.compare(baseline, candidate)
    assert result.confidence == "high"


# --- L907-910: ABGate.compare recommendations ---

def test_ab_gate_compare_keep_baseline() -> None:
    result = ABGate.compare([0.9, 0.9, 0.9], [0.5, 0.5, 0.5])
    assert result.recommendation == "keep baseline"


def test_ab_gate_compare_no_significant_difference() -> None:
    result = ABGate.compare([0.5, 0.5, 0.5], [0.51, 0.51, 0.51])
    assert result.recommendation == "no significant difference"


# --- L928-931: ABGate.canary_check ---

def test_ab_gate_canary_check_empty() -> None:
    assert ABGate.canary_check([]) is False


def test_ab_gate_canary_check_passes() -> None:
    assert ABGate.canary_check([0.9, 0.9, 0.9, 0.9, 0.7]) is True


def test_ab_gate_canary_check_fails() -> None:
    assert ABGate.canary_check([0.5, 0.5, 0.5, 0.9]) is False


# --- L969-972: DistributedExecutor.process_one exception ---

def test_distributed_executor_worker_exception() -> None:
    executor = DistributedExecutor()
    executor.submit("j1", {"input": "boom"})

    def boom(_scenario: dict) -> dict:
        raise ValueError("kaboom")

    result = executor.process_one(boom)
    assert result is None
    assert executor.pending() == 0
    # verify job status and error stored
    assert executor._jobs[0]["status"] == "failed"
    assert executor._results["j1"] == {"error": "kaboom"}


def test_distributed_executor_process_empty_queue() -> None:
    executor = DistributedExecutor()
    result = executor.process_one(lambda s: {"ok": True})
    assert result is None


# --- L1019-1029: TelemetryExporter.build_grafana_dashboard ---

def test_telemetry_grafana_dashboard() -> None:
    dashboard = TelemetryExporter.build_grafana_dashboard(
        "EvalForge Overview", ["scenarios.passed", "scenarios.failed", "latency.ms"],
    )
    assert dashboard["title"] == "EvalForge Overview"
    assert dashboard["schemaVersion"] == 37
    assert len(dashboard["panels"]) == 3
    assert dashboard["panels"][0]["title"] == "scenarios.passed"
    assert dashboard["panels"][0]["type"] == "stat"
    assert dashboard["panels"][0]["targets"][0]["expr"] == "evalforge_scenarios_passed"
    assert dashboard["panels"][2]["gridPos"]["x"] == 0
    assert dashboard["panels"][2]["gridPos"]["y"] == 8


def test_telemetry_grafana_dashboard_empty() -> None:
    dashboard = TelemetryExporter.build_grafana_dashboard("Empty", [])
    assert dashboard["panels"] == []


# --- L1082: GovernancePolicy.can unknown role ---

def test_governance_unknown_role() -> None:
    assert GovernancePolicy.can("nonexistent", "run") is False


# --- L1096-1097: GovernancePolicy.require_role raises PermissionError ---

def test_governance_require_role_raises() -> None:
    with pytest.raises(PermissionError, match="Role 'viewer' cannot perform 'admin'"):
        GovernancePolicy.require_role("viewer", "admin")


def test_governance_require_role_passes() -> None:
    GovernancePolicy.require_role("admin", "admin")


# --- L81-82, L196, L270 edge coverage ---

def test_budget_optimizer_empty_results() -> None:
    profile = BudgetOptimizer.find_minimal_budget([], 0.8)
    assert profile.name == "unbounded"


def test_stress_tester_p99_small_n() -> None:
    result = StressTester.analyze_durations([100, 200, 300, 400, 500])
    assert result.p99_ms == 500


def test_multi_agent_evaluator_empty() -> None:
    result = MultiAgentEvaluator.evaluate([])
    assert result["agents_involved"] == 0
    assert result["total_interactions"] == 0
    assert result["passed"] is True


def test_model_matrix_best_by_cost() -> None:
    runner = ModelMatrixRunner()
    runner.add_result("openai", "gpt-4o", 0.9, 0.05, 2000)
    runner.add_result("anthropic", "claude", 0.95, 0.03, 2500)
    best = runner.best_by_cost()
    assert best is not None
    assert best.provider == "anthropic"
    assert best.avg_cost_usd == 0.03


def test_html_report_scenario_deep_link_no_base() -> None:
    link = HTMLReportEnhancer.scenario_deep_link("s1")
    assert link == "#scenario-s1"


# --- L269: BudgetOptimizer successful profile match ---

def test_budget_optimizer_with_matching_results() -> None:
    results = [
        {"passed": True, "steps": 2, "cost_usd": 0.005},
        {"passed": True, "steps": 5, "cost_usd": 0.02},
    ]
    profile = BudgetOptimizer.find_minimal_budget(results, 0.8)
    assert profile.name in ("minimal", "moderate")


# --- L350: ModelMatrixRunner.best_by_score non-empty ---

def test_model_matrix_best_by_score_non_empty() -> None:
    runner = ModelMatrixRunner()
    runner.add_result("openai", "gpt-4o", 0.9, 0.05, 2000)
    runner.add_result("anthropic", "claude", 0.95, 0.06, 2500)
    best = runner.best_by_score()
    assert best is not None
    assert best.provider == "anthropic"
    assert best.avg_score == 0.95


# --- L546, 549-550: HTMLReportEnhancer.diff_view with changes ---

def test_html_report_diff_view_with_changes() -> None:
    diff = HTMLReportEnhancer.diff_view({"a": 1, "b": 2}, {"a": 2, "c": 3})
    assert "<td>a</td>" in diff
    assert "<td>1</td>" in diff
    assert "<td>2</td>" in diff
    assert "<td>b</td>" in diff
    assert "<td>c</td>" in diff
    assert diff.startswith("<table>")
    assert diff.endswith("</table>")


# --- L568: DataLakeExporter.to_jsonl ---

def test_datalake_to_jsonl() -> None:
    result = DataLakeExporter.to_jsonl([{"a": 1}, {"a": 2}])
    assert result.count("\n") == 1


# --- L706, 730, 738: TutorialRegistry ---

def test_tutorial_registry_all() -> None:
    reg = TutorialRegistry()
    assert len(reg.all()) == 3


def test_tutorial_registry_list_by_tag() -> None:
    reg = TutorialRegistry()
    assert len(reg.list_by_tag("beginner")) == 1
    assert len(reg.list_by_tag("intermediate")) == 1
    assert len(reg.list_by_tag("advanced")) == 1
    assert len(reg.list_by_tag("nonexistent")) == 0


# --- L753: VSCodeIntegration.generate_tasks_json ---

def test_vscode_generates_tasks() -> None:
    tasks = VSCodeIntegration.generate_tasks_json()
    assert "evalforge: run scenarios" in tasks
    assert "evalforge: validate pack" in tasks


# --- L790: GitHubPRGate.generate_check_payload ---

def test_github_pr_gate() -> None:
    payload = GitHubPRGate.generate_check_payload("success", "All passed", {"score": 1.0})
    assert payload["conclusion"] == "success"
    assert payload["output"]["summary"] == "All passed"
    assert '"score"' in payload["output"]["text"]


def test_github_pr_gate_no_details() -> None:
    payload = GitHubPRGate.generate_check_payload("failure", "Some failed")
    assert payload["conclusion"] == "failure"
    assert payload["output"]["text"] == "{}"


# --- L845-852: FlakinessProfiler with ≥2 scores (non-flaky variant) ---

def test_flakiness_profiler_stable() -> None:
    result = FlakinessProfiler.analyze("s1", [1.0, 1.0, 1.0, 1.0])
    assert result.total_runs == 4
    assert result.flake_rate == 0.0
    assert result.score_variance == 0.0
    assert result.is_flaky is False


def test_flakiness_profiler_flaky() -> None:
    result = FlakinessProfiler.analyze("s1", [0.5, 0.5, 0.5, 0.9], threshold=0.1)
    assert result.flake_rate > 0


# --- L966-968: DistributedExecutor.process_one successful ---

def test_distributed_executor_process_success() -> None:
    executor = DistributedExecutor()
    executor.submit("j1", {"input": "hello"})
    result = executor.process_one(lambda s: {"output": s["input"].upper()})
    assert result == {"output": "HELLO"}
    assert executor._jobs[0]["status"] == "completed"
    assert executor.pending() == 0


# --- L998-1004: TelemetryExporter.to_prometheus_metrics ---

def test_telemetry_prometheus_metrics() -> None:
    output = TelemetryExporter.to_prometheus_metrics({
        "scenarios.passed": 10.0,
        "scenarios.failed": 2.0,
    })
    assert "evalforge_scenarios_passed 10.0" in output
    assert "evalforge_scenarios_failed 2.0" in output
    assert "# HELP" in output
    assert "# TYPE" in output


def test_telemetry_prometheus_metrics_empty() -> None:
    output = TelemetryExporter.to_prometheus_metrics({})
    assert output == "\n"
