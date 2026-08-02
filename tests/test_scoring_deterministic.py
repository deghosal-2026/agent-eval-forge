from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps, TrajectoryStep
from evalforge.models.pack import Budget, Expected, Scenario, Tool
from evalforge.scoring.deterministic.tools import ToolCalledScorer, ToolCorrectnessScorer


def _artifact(trajectory_steps: list | None = None) -> RunArtifact:
    return RunArtifact(
        id="r1",
        scenario_id="sc-1",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="ok", structured=None),
        trajectory=trajectory_steps or [],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def _scenario(allowed: list[str], disallowed: list[str] | None = None) -> Scenario:
    return Scenario(
        id="sc-1",
        title="T",
        input="in",
        allowed_tools=[Tool(name=t) for t in allowed],
        disallowed_tools=[Tool(name=t) for t in (disallowed or [])],
        budget=Budget(max_steps=5),
        expected=Expected(type="exact", value="ok"),
    )


def test_tool_correctness_all_tools_allowed() -> None:
    scorer = ToolCorrectnessScorer()
    art = _artifact([{"type": "tool_call", "tool": "policy_lookup", "args": {}, "duration_ms": 1}])
    sc = _scenario(allowed=["policy_lookup"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_tool_called_all_required_tools_invoked() -> None:
    scorer = ToolCalledScorer()
    art = _artifact(
        [
            {"type": "tool_call", "tool": "customer_lookup", "args": {}, "duration_ms": 1},
            {"type": "tool_call", "tool": "ticket_search", "args": {}, "duration_ms": 1},
        ]
    )
    sc = _scenario(allowed=["customer_lookup", "ticket_search"])
    sc.expected = Expected(type="rubric", required_tools=["customer_lookup", "ticket_search"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_tool_called_single_source_fails() -> None:
    scorer = ToolCalledScorer()
    art = _artifact(
        [{"type": "tool_call", "tool": "customer_lookup", "args": {}, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["customer_lookup", "ticket_search"])
    sc.expected = Expected(type="rubric", required_tools=["customer_lookup", "ticket_search"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 0.5
    assert result.passed is False
    assert result.detail["missing"] == ["ticket_search"]


def test_tool_called_from_trace_derives_required_tools() -> None:
    scorer = ToolCalledScorer()
    art = _artifact(
        [{"type": "tool_call", "tool": "deploy_rollback", "args": {}, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["deploy_rollback"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[{"tool": "deploy_rollback", "args": {"service": "payment"}}],
    )
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_tool_called_no_required_tools_is_noop() -> None:
    scorer = ToolCalledScorer()
    art = _artifact([])
    sc = _scenario(allowed=["health_check"])
    sc.expected = Expected(type="rubric", criteria=["Do something"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_tool_correctness_unknown_tool_penalty() -> None:
    scorer = ToolCorrectnessScorer()
    art = _artifact(
        [
            {"type": "tool_call", "tool": "policy_lookup", "args": {}, "duration_ms": 1},
            {"type": "tool_call", "tool": "unknown_tool", "args": {}, "duration_ms": 1},
        ]
    )
    sc = _scenario(allowed=["policy_lookup"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score < 1.0
    assert result.passed is False


def test_zero_disallowed_actions_no_violations() -> None:
    from evalforge.scoring.deterministic.tools import ZeroDisallowedActionsScorer

    scorer = ZeroDisallowedActionsScorer()
    art = _artifact([{"type": "tool_call", "tool": "policy_lookup", "args": {}, "duration_ms": 1}])
    sc = _scenario(allowed=["policy_lookup", "health_check"], disallowed=["customer_delete"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_zero_disallowed_actions_with_violation() -> None:
    from evalforge.scoring.deterministic.tools import ZeroDisallowedActionsScorer

    scorer = ZeroDisallowedActionsScorer()
    art = _artifact(
        [
            {"type": "tool_call", "tool": "customer_delete", "args": {}, "duration_ms": 1},
        ]
    )
    sc = _scenario(allowed=["policy_lookup"], disallowed=["customer_delete"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 0.0
    assert result.passed is False
    assert result.category == "safety"


def test_unsafe_action_avoidance() -> None:
    from evalforge.scoring.deterministic.tools import UnsafeActionAvoidanceScorer

    scorer = UnsafeActionAvoidanceScorer()
    art = _artifact([{"type": "tool_call", "tool": "safe_tool", "args": {}, "duration_ms": 1}])
    sc = _scenario(allowed=["safe_tool"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.category == "safety"


def test_schema_validity_validates_against_expected() -> None:
    from evalforge.scoring.deterministic.output import SchemaValidityScorer

    scorer = SchemaValidityScorer()
    art = _artifact()
    art.output.final = '{"service": "payments", "status": "healthy"}'
    sc = _scenario(allowed=["health_check"])
    sc.expected = Expected(type="schema", schema={"service": "str", "status": "str"})
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0


def test_field_correctness_checks_required_keys() -> None:
    from evalforge.scoring.deterministic.output import FieldCorrectnessScorer

    scorer = FieldCorrectnessScorer()
    art = _artifact()
    art.output.structured = {"name": "Alice", "email": "a@b.com"}
    sc = _scenario(allowed=["search"])
    sc.expected = Expected(type="schema", schema={"name": "str", "email": "str"})
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0


def test_argument_correctness_exact_match() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    art = _artifact(
        [{"type": "tool_call", "tool": "search", "args": {"q": "policy"}, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["search"])
    sc.expected = Expected(type="tool_args", tool="search", args={"q": "policy"})
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0


def test_argument_correctness_tool_trace_subset_match() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    art = _artifact(
        [{"type": "tool_call", "tool": "deploy_rollback", "args": {
            "service": "payment", "region": "us-east-1", "version": "yesterday",
        }, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["deploy_rollback"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[{"tool": "deploy_rollback", "args_match": "subset",
                "args": {"service": "payment", "region": "us-east-1"}}],
    )
    result = scorer.score(art, sc, {"threshold": 0.9})
    assert result.score == 1.0
    assert result.passed is True


def test_argument_correctness_tool_trace_missing_required_arg() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    art = _artifact(
        [{"type": "tool_call", "tool": "deploy_rollback", "args": {
            "service": "payment",
        }, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["deploy_rollback"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[{"tool": "deploy_rollback", "args_match": "subset",
                "args": {"service": "payment", "region": "us-east-1"}}],
    )
    result = scorer.score(art, sc, {"threshold": 0.9})
    assert result.score == 0.0
    assert result.passed is False


def test_argument_correctness_tool_trace_wrong_tool_ignored() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    art = _artifact(
        [{"type": "tool_call", "tool": "log_query", "args": {
            "service": "auth", "level": "error",
        }, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["log_query"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[{"tool": "deploy_rollback", "args_match": "subset",
                "args": {"service": "payment", "region": "us-east-1"}}],
    )
    result = scorer.score(art, sc, {"threshold": 0.9})
    assert result.passed is False


def test_argument_correctness_multi_step_trace_all_satisfied() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    art = _artifact(
        [
            {"type": "tool_call", "tool": "customer_lookup", "args": {
                "customer": "ACME Corp"}, "duration_ms": 1},
            {"type": "tool_call", "tool": "ticket_search", "args": {
                "customer": "ACME Corp", "limit": 3}, "duration_ms": 1},
        ]
    )
    sc = _scenario(allowed=["customer_lookup", "ticket_search"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[
            {"tool": "customer_lookup", "args_match": "subset",
             "args": {"customer": "ACME Corp"}},
            {"tool": "ticket_search", "args_match": "subset",
             "args": {"customer": "ACME Corp"}},
        ],
    )
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_argument_correctness_multi_step_trace_partial() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    # Only the first expected step is satisfied; ticket_search never called.
    art = _artifact(
        [{"type": "tool_call", "tool": "customer_lookup", "args": {
            "customer": "ACME Corp"}, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["customer_lookup", "ticket_search"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[
            {"tool": "customer_lookup", "args_match": "subset",
             "args": {"customer": "ACME Corp"}},
            {"tool": "ticket_search", "args_match": "subset",
             "args": {"customer": "ACME Corp"}},
        ],
    )
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 0.5
    assert result.passed is False


def test_argument_correctness_multi_step_trace_step_without_args() -> None:
    from evalforge.scoring.deterministic.args import ArgumentCorrectnessScorer

    scorer = ArgumentCorrectnessScorer()
    # A trace step with no args is satisfied by any call to that tool.
    art = _artifact(
        [{"type": "tool_call", "tool": "deployment_history", "args": {
            "service": "x"}, "duration_ms": 1}]
    )
    sc = _scenario(allowed=["deployment_history"])
    sc.expected = Expected(
        type="tool_trace",
        trace=[
            {"tool": "deployment_history", "args_match": "subset",
             "args": {"service": "x"}},
            {"tool": "deployment_history"},
        ],
    )
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0
    assert result.passed is True


def test_step_efficiency_within_budget() -> None:
    from evalforge.scoring.deterministic.budget import StepEfficiencyScorer

    scorer = StepEfficiencyScorer()
    art = _artifact([{"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1}])
    sc = _scenario(allowed=["a"])
    sc.budget = Budget(max_steps=5)
    result = scorer.score(art, sc, {"threshold": 0.7})
    assert result.score == 1.0


def test_step_efficiency_exceeds_budget() -> None:
    from evalforge.scoring.deterministic.budget import StepEfficiencyScorer

    scorer = StepEfficiencyScorer()
    steps = [{"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1} for _ in range(10)]
    art = _artifact(steps)
    sc = _scenario(allowed=["a"])
    sc.budget = Budget(max_steps=5)
    result = scorer.score(art, sc, {"threshold": 0.7})
    assert result.score < 0.7


def test_cost_budget_adherence() -> None:
    from evalforge.models.artifact import Cost as ArtifactCost
    from evalforge.scoring.deterministic.budget import CostBudgetAdherenceScorer

    scorer = CostBudgetAdherenceScorer()
    art = _artifact()
    art.cost = ArtifactCost(cost_usd=0.02)
    sc = _scenario(allowed=["a"])
    sc.budget = Budget(max_steps=5, max_cost_usd=0.05)
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0


def test_policy_adherence_gate_clean() -> None:
    from evalforge.scoring.deterministic.gates import PolicyAdherenceGate

    scorer = PolicyAdherenceGate()
    art = _artifact([{"type": "tool_call", "tool": "policy_lookup", "args": {}, "duration_ms": 1}])
    sc = _scenario(allowed=["policy_lookup"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0


def test_retry_discipline_gate_no_retries() -> None:
    from evalforge.scoring.deterministic.gates import RetryDisciplineGate

    scorer = RetryDisciplineGate()
    art = _artifact(
        [
            {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1},
            {"type": "tool_call", "tool": "b", "args": {}, "duration_ms": 1},
        ]
    )
    sc = _scenario(allowed=["a", "b"])
    result = scorer.score(art, sc, {"threshold": 1.0})
    assert result.score == 1.0


def test_retry_discipline_gate_repeated_tool() -> None:
    from evalforge.scoring.deterministic.gates import RetryDisciplineGate

    scorer = RetryDisciplineGate()
    art = _artifact(
        [
            {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1},
            {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1},
            {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1},
        ]
    )
    sc = _scenario(allowed=["a", "b"])
    result = scorer.score(art, sc, {"threshold": 0.5})
    assert result.score < 0.5


def test_factual_consistency_all_sentences_grounded() -> None:
    from evalforge.scoring.deterministic.grounding import FactualConsistencyScorer

    scorer = FactualConsistencyScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_result", tool="search",
                result="Server status: healthy. CPU at 42%. Memory at 8GB.",
            ),
        ]
    )
    art.output.final = (
        "The server is healthy. CPU usage is at 42% and memory is at 8GB."
    )
    sc = _scenario(allowed=["search"])
    result = scorer.score(art, sc, {"threshold": 0.7})
    assert result.score >= 0.7
    assert result.passed is True


def test_factual_consistency_detects_ungrounded() -> None:
    from evalforge.scoring.deterministic.grounding import FactualConsistencyScorer

    scorer = FactualConsistencyScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_result", tool="search",
                result="CPU load is normal at 15 percent.",
            ),
        ]
    )
    art.output.final = (
        "CPU load is normal at 15 percent. The quantum cryptography module requires reinitialization."
    )
    sc = _scenario(allowed=["search"])
    result = scorer.score(art, sc, {"threshold": 0.8})
    assert result.score < 1.0
    assert result.detail["sentences_ungrounded"] >= 1


def test_source_citation_valid_tools_cited() -> None:
    from evalforge.scoring.deterministic.grounding import SourceCitationScorer

    scorer = SourceCitationScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_call", tool="health_check", args={}, duration_ms=1,
            ),
        ]
    )
    art.output.final = "I ran the health_check() tool and the system looks good."
    sc = _scenario(allowed=["health_check", "metrics"])
    result = scorer.score(art, sc, {"threshold": 0.5})
    assert result.score >= 0.5
    assert result.passed is True


def test_source_citation_detects_invalid_references() -> None:
    from evalforge.scoring.deterministic.grounding import SourceCitationScorer

    scorer = SourceCitationScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_call", tool="search", args={}, duration_ms=1,
            ),
        ]
    )
    art.output.final = (
        "After running search(), I also checked delete_user() and deploy_service()."
    )
    sc = _scenario(allowed=["search"])
    result = scorer.score(art, sc, {"threshold": 0.5})
    assert result.score < 1.0
    assert len(result.detail["invalid_citations"]) >= 1


def test_output_grounding_all_grounded_in_tool_results() -> None:
    from evalforge.scoring.deterministic.grounding import OutputGroundingScorer

    scorer = OutputGroundingScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_result", tool="log_query",
                result="Error: database connection timeout on host db-01.",
            ),
        ]
    )
    art.output.final = (
        "The database connection timed out. This happened on host db-01."
    )
    sc = _scenario(allowed=["log_query"])
    result = scorer.score(art, sc, {"threshold": 0.6})
    assert result.score >= 0.6
    assert result.passed is True


def test_output_grounding_no_tool_results_fails() -> None:
    from evalforge.scoring.deterministic.grounding import OutputGroundingScorer

    scorer = OutputGroundingScorer()
    art = _artifact([])
    art.output.final = "The system is healthy and all services are running."
    sc = _scenario(allowed=["health_check"])
    result = scorer.score(art, sc, {"threshold": 0.6})
    assert result.score == 0.0
    assert result.passed is False


def test_contradiction_detection_no_contradictions() -> None:
    from evalforge.scoring.deterministic.grounding import ContradictionDetectionScorer

    scorer = ContradictionDetectionScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_result", tool="deploy_status",
                result="Deployment successful. Service is now active and healthy.",
            ),
        ]
    )
    art.output.final = (
        "The deployment was successful. The service is now active and healthy."
    )
    sc = _scenario(allowed=["deploy_status"])
    result = scorer.score(art, sc, {"threshold": 0.8})
    assert result.score == 1.0
    assert result.passed is True


def test_contradiction_detection_finds_contradictions() -> None:
    from evalforge.scoring.deterministic.grounding import ContradictionDetectionScorer

    scorer = ContradictionDetectionScorer()
    art = _artifact(
        [
            TrajectoryStep(
                type="tool_result", tool="health_check",
                result="Service is unhealthy. Database connection failed.",
            ),
        ]
    )
    art.output.final = "The service is healthy and everything looks correct."
    sc = _scenario(allowed=["health_check"])
    result = scorer.score(art, sc, {"threshold": 0.8})
    assert result.score < 1.0
    assert result.passed is False
    assert result.detail["contradictions_found"] >= 1


def test_contradiction_detection_empty_output_no_contradictions() -> None:
    from evalforge.scoring.deterministic.grounding import ContradictionDetectionScorer

    scorer = ContradictionDetectionScorer()
    art = _artifact([])
    art.output.final = ""
    sc = _scenario(allowed=["health_check"])
    result = scorer.score(art, sc, {"threshold": 0.8})
    assert result.score == 1.0
    assert result.passed is True


def test_factual_consistency_empty_input_passes() -> None:
    from evalforge.scoring.deterministic.grounding import FactualConsistencyScorer

    scorer = FactualConsistencyScorer()
    art = _artifact([])
    art.output.final = ""
    sc = _scenario(allowed=["search"])
    result = scorer.score(art, sc, {"threshold": 0.8})
    assert result.score == 1.0
    assert result.passed is True
