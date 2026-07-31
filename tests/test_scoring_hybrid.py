import pytest

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import Budget, Expected, Scenario, Tool
from evalforge.scoring.deterministic import gates  # noqa: F401 — register gate scorers
from evalforge.scoring.hybrid import HybridScorer
from evalforge.scoring.judge import scorers  # noqa: F401 — register judge scorers
from evalforge.scoring.judge.mock import MockJudge
from evalforge.scoring.registry import get_scorer


def _artifact() -> RunArtifact:
    return RunArtifact(
        id="r1", scenario_id="sc-1",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="ok", structured=None),
        trajectory=[], cost=Cost(), status="completed", error=None, agent={},
    )


def _scenario(allowed: list[str] | None = None) -> Scenario:
    return Scenario(
        id="sc-1", title="T", input="in",
        allowed_tools=[Tool(name=t) for t in (allowed or ["t"])],
        budget=Budget(max_steps=5),
        expected=Expected(type="exact", value="ok"),
    )


def test_hybrid_gate_pass_skips_judge() -> None:
    gate = get_scorer("policy_adherence_gate")
    assert gate is not None
    hybrid = HybridScorer("policy_adherence", gate, MockJudge(score=0.0))
    art = _artifact()
    step = type("Step", (), {"type": "tool_call", "tool": "t", "args": {}, "duration_ms": 1})()
    art.trajectory = [step]
    sc = _scenario(allowed=["t"])
    result = hybrid.score(art, sc, {"threshold": 1.0})
    assert result.source == "deterministic"  # gate passed, judge skipped
    assert result.score == 1.0


def test_hybrid_gate_fail_skips_judge() -> None:
    gate = get_scorer("policy_adherence_gate")
    assert gate is not None
    hybrid = HybridScorer("policy_adherence", gate, MockJudge(score=0.0))
    art = _artifact()
    step = type("Step", (), {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1})()
    art.trajectory = [step]
    sc = _scenario(allowed=["t"])
    sc.disallowed_tools = [Tool(name="danger")]
    result = hybrid.score(art, sc, {"threshold": 1.0})
    assert result.source == "deterministic"  # gate clearly failed, judge skipped
    assert result.score == 0.0


def test_hybrid_gate_inconclusive_falls_back_to_judge() -> None:
    gate = get_scorer("retry_discipline_gate")
    assert gate is not None
    hybrid = HybridScorer("retry_discipline", gate, MockJudge(score=0.9))
    art = _artifact()
    step = type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})
    art.trajectory = [step(), step(), step()]
    sc = _scenario(allowed=["a", "b"])
    result = hybrid.score(art, sc, {"threshold": 1.0})
    assert result.source == "judge"  # partial gate score is inconclusive → judge decides
    assert result.score == 0.9


def test_hybrid_no_scorer_in_registry() -> None:
    gate = get_scorer("policy_adherence_gate")
    assert gate is not None
    hybrid = HybridScorer("nonexistent", gate, MockJudge(score=0.0))
    with pytest.raises(ValueError, match="no judge scorer"):
        hybrid.score(_artifact(), _scenario(), {})
