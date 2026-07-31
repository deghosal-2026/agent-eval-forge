from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import Budget, Expected, Scenario, Tool
from evalforge.scoring.deterministic.tools import ToolCorrectnessScorer


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
