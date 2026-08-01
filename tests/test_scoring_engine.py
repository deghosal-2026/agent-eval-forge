import pytest

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)

# Import scorer modules to register them
from evalforge.scoring.base import Scorer
from evalforge.scoring.deterministic import (
    gates,  # noqa: F401
    tools,  # noqa: F401
)
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge import scorers  # noqa: F401
from evalforge.scoring.judge.mock import MockJudge
from evalforge.scoring.registry import register_scorer, get_scorer, SCORERS
from evalforge.scoring.result import RunScore, ScoreResult


def _pack() -> ScenarioPack:
    return ScenarioPack(
        pack=PackMetadata(name="test", version="1.0.0"),
        scenarios=[
            Scenario(
                id="sc-1",
                title="T",
                input="i",
                goal="g",
                allowed_tools=[Tool(name="a")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["retrieval"],
            ),
        ],
    )


def _artifact(final: str = "ok", scenario_id: str = "sc-1") -> RunArtifact:
    return RunArtifact(
        id=f"r1-{scenario_id}",
        scenario_id=scenario_id,
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final=final, structured=None),
        trajectory=[],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def test_score_run_returns_run_score() -> None:
    engine = ScoringEngine(_pack())
    result = engine.score_run([_artifact()])
    assert isinstance(result, RunScore)
    assert "sc-1" in result.scenario_scores


def test_score_run_resolves_metrics() -> None:
    engine = ScoringEngine(_pack())
    result = engine.score_run([_artifact()])
    ss = result.scenario_scores["sc-1"]
    assert "tool_correctness" in ss.metric_results
    sr = ss.metric_results["tool_correctness"]
    assert sr.metric == "tool_correctness"
    assert sr.score is not None


def test_score_run_unknown_metric_raises_config_error() -> None:
    pack = _pack()
    pack.scenarios[0].metrics = {"bogus": Metric(threshold=0.5)}
    engine = ScoringEngine(pack)
    with pytest.raises(ValueError, match="unknown metric"):
        engine.score_run([_artifact()])


def test_score_run_exit_code_0_all_pass() -> None:
    engine = ScoringEngine(_pack())
    result = engine.score_run([_artifact()])
    assert result.exit_code == 0


def test_score_run_exit_code_4_safety_violation() -> None:
    pack = _pack()
    pack.scenarios[0].disallowed_tools = [Tool(name="danger")]
    pack.scenarios[0].metrics = {"zero_disallowed_actions": Metric(threshold=1.0)}
    engine = ScoringEngine(pack)
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1})(),
    ]
    result = engine.score_run([art])
    assert result.exit_code == 4
    assert len(result.safety_violations) > 0


def test_score_run_exit_code_1_threshold_breach() -> None:
    pack = _pack()
    pack.scenarios[0].allowed_tools = [Tool(name="a"), Tool(name="b"), Tool(name="c")]
    pack.scenarios[0].metrics = {"tool_correctness": Metric(threshold=1.0)}
    engine = ScoringEngine(pack)
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    result = engine.score_run([art])
    assert result.exit_code == 1


def test_score_hybrid_metric_with_judge() -> None:
    pack = _pack()
    pack.scenarios[0].metrics = {"policy_adherence": Metric(threshold=1.0)}
    pack.scenarios[0].allowed_tools = [Tool(name="a")]
    pack.scenarios[0].disallowed_tools = [Tool(name="danger")]
    engine = ScoringEngine(pack)
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    judge = MockJudge(score=1.0, rationale="all good")
    result = engine.score_run([art], judge=judge)
    assert result.exit_code == 0


def test_score_hybrid_metric_skipped_when_gate_missing() -> None:
    """When a hybrid metric has no registered gate, engine continues gracefully."""
    from evalforge.scoring.engine import _HYBRID_METRICS
    orig = _HYBRID_METRICS.copy()
    _HYBRID_METRICS.add("nonexistent_gate_metric")
    try:
        pack = _pack()
        pack.scenarios[0].metrics["nonexistent_gate_metric"] = Metric(threshold=0.5)
        engine = ScoringEngine(pack)
        art = _artifact()
        # Bypass validation since nonexistent_gate_metric is in _HYBRID_METRICS
        ss = engine._score_scenario(pack.scenarios[0], art, judge=None)
        assert "tool_correctness" in ss.metric_results
        assert "nonexistent_gate_metric" not in ss.metric_results
    finally:
        _HYBRID_METRICS.clear()
        _HYBRID_METRICS.update(orig)


def test_score_hybrid_metric_no_judge() -> None:
    """Hybrid metric with no judge produces a ScoreResult with error and exit code 3."""
    pack = _pack()
    pack.scenarios[0].metrics = {"policy_adherence": Metric(threshold=1.0)}
    pack.scenarios[0].allowed_tools = [Tool(name="a")]
    pack.scenarios[0].disallowed_tools = [Tool(name="danger")]
    engine = ScoringEngine(pack)
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    result = engine.score_run([art])
    ss = result.scenario_scores["sc-1"]
    sr = ss.metric_results["policy_adherence"]
    assert sr.score is None
    assert sr.error == "judge not configured"
    assert result.exit_code == 3


def test_non_hybrid_metric_unknown_scorer_skipped() -> None:
    """When a non-hybrid metric has no registered scorer, engine continues gracefully."""
    pack = _pack()
    engine = ScoringEngine(pack)
    scenario = pack.scenarios[0]
    scenario.metrics["nonexistent_metric"] = Metric(threshold=0.5)
    # Bypass validation by calling _score_scenario directly
    art = _artifact()
    ss = engine._score_scenario(scenario, art, judge=None)
    # The nonexistent metric is skipped, only tool_correctness is scored
    assert "tool_correctness" in ss.metric_results
    assert "nonexistent_metric" not in ss.metric_results


def test_scorer_exception_caught(tmp_path) -> None:
    """When a scorer raises, engine produces a ScoreResult with error."""
    from evalforge.scoring.registry import SCORERS
    orig = SCORERS.copy()
    try:
        @register_scorer
        class RaisingScorer(Scorer):
            name = "raises_on_purpose"
            category = "correctness"
            def score(self, artifact, scenario, metric_config):
                raise RuntimeError("boom")
        pack = _pack()
        pack.scenarios[0].metrics = {"raises_on_purpose": Metric(threshold=0.5)}
        engine = ScoringEngine(pack)
        art = _artifact()
        result = engine.score_run([art])
        ss = result.scenario_scores["sc-1"]
        sr = ss.metric_results["raises_on_purpose"]
        assert sr.score is None
        assert sr.error == "scorer failed: boom"
    finally:
        SCORERS.clear()
        SCORERS.update(orig)


def test_score_run_aggregates_two_scenarios() -> None:
    pack = _pack()
    pack.scenarios.append(
        Scenario(
            id="sc-2",
            title="T2",
            input="i2",
            goal="g2",
            allowed_tools=[Tool(name="a")],
            budget=Budget(max_steps=5),
            expected=Expected(type="exact", value="ok"),
            metrics={"tool_correctness": Metric(threshold=1.0)},
        ),
    )
    engine = ScoringEngine(pack)
    arts = [_artifact(), _artifact(scenario_id="sc-2")]
    result = engine.score_run(arts)
    assert len(result.scenario_scores) == 2
    assert result.totals["passed"] == 2
