from evalforge.scoring.deterministic.tools import ToolCorrectnessScorer
from evalforge.models.artifact import RunArtifact, RunTimestamps, RunOutput, Cost
from evalforge.models.pack import Scenario, Budget, Tool, Expected


def _artifact(trajectory_steps: list | None = None) -> RunArtifact:
    return RunArtifact(
        id="r1", scenario_id="sc-1",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="ok", structured=None),
        trajectory=trajectory_steps or [],
        cost=Cost(), status="completed", error=None,
        agent={},
    )


def _scenario(allowed: list[str], disallowed: list[str] | None = None) -> Scenario:
    return Scenario(
        id="sc-1", title="T", input="in",
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
    art = _artifact([
        {"type": "tool_call", "tool": "policy_lookup", "args": {}, "duration_ms": 1},
        {"type": "tool_call", "tool": "unknown_tool", "args": {}, "duration_ms": 1},
    ])
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
    art = _artifact([
        {"type": "tool_call", "tool": "customer_delete", "args": {}, "duration_ms": 1},
    ])
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