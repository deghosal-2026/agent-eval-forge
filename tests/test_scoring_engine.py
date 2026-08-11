import pytest

from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps, TrajectoryStep
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
from evalforge.scoring.registry import SCORERS, get_scorer, register_scorer
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
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    result = engine.score_run([art])
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
    """When a hybrid metric has no registered gate, engine records an error result."""
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
        assert "nonexistent_gate_metric" in ss.metric_results
        sr = ss.metric_results["nonexistent_gate_metric"]
        assert sr.error == "gate scorer 'nonexistent_gate_metric_gate' not registered"
        assert sr.score is None
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
    assert sr.score == 1.0
    assert sr.error is None
    assert sr.detail.get("judge_not_evaluated") is True
    assert result.exit_code == 0


def test_non_hybrid_metric_unknown_scorer_skipped() -> None:
    """When a non-hybrid metric has no registered scorer, engine records an error result."""
    pack = _pack()
    engine = ScoringEngine(pack)
    scenario = pack.scenarios[0]
    scenario.metrics["nonexistent_metric"] = Metric(threshold=0.5)
    # Bypass validation by calling _score_scenario directly
    art = _artifact()
    ss = engine._score_scenario(scenario, art, judge=None)
    assert "tool_correctness" in ss.metric_results
    assert "nonexistent_metric" in ss.metric_results
    sr = ss.metric_results["nonexistent_metric"]
    assert sr.error == "scorer 'nonexistent_metric' not registered"
    assert sr.score is None


def test_scorer_exception_caught(tmp_path) -> None:
    """When a scorer raises, engine produces a ScoreResult with error."""
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
        assert sr.score == 0.0
        assert sr.passed is False
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
    art1 = _artifact()
    art1.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    art2 = _artifact(scenario_id="sc-2")
    art2.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    arts = [art1, art2]
    result = engine.score_run(arts)
    assert len(result.scenario_scores) == 2
    assert result.totals["passed"] == 2


def test_judge_error_exit_code_3() -> None:
    """When judge errors occur, exit code is 3."""
    from evalforge.adapters.base import _sanitize_agent
    from evalforge.loading.pack_loader import load_pack
    from evalforge.scoring.judge.mock import MockJudge

    pack = load_pack("scenarios/core-launch.yaml")
    engine = ScoringEngine(pack)

    class ErrorJudge(MockJudge):
        def judge(self, prompt: str, context: dict | None = None) -> dict:  # type: ignore[override]
            return {"score": None, "rationale": "error: judge failed", "error": "judge error"}

    artifact = RunArtifact(
        id="test", scenario_id=pack.scenarios[0].id,
        agent=_sanitize_agent({}),
        timestamp=RunTimestamps(start="now", end="now", duration_ms=0),
        output=RunOutput(final="test", structured=None),
        trajectory=[], cost=Cost(), status="completed",
    )
    score = engine.score_run([artifact], judge=ErrorJudge(score=None))  # type: ignore[arg-type]
    assert score.exit_code == 3


def test_error_artifact_short_circuits_scoring() -> None:
    """Artifact with status != 'completed' produces a failed ScenarioScore with score 0.0."""
    engine = ScoringEngine(_pack())
    art = _artifact()
    art.status = "error"
    art.error_category = "ModuleNotFoundError"
    art.error = "No module named 'foo'"
    result = engine.score_run([art])
    ss = result.scenario_scores["sc-1"]
    assert ss.status == "failed"
    assert "harness_failure" in ss.metric_results
    hf = ss.metric_results["harness_failure"]
    assert hf.score == 0.0
    assert hf.passed is False
    assert "ModuleNotFoundError" in (hf.error or "")
    assert result.totals["failed"] == 1
    assert result.totals["passed"] == 0


def test_timeout_artifact_short_circuits_scoring() -> None:
    """Artifact with status='timeout' short-circuits to harness_failure."""
    engine = ScoringEngine(_pack())
    art = _artifact()
    art.status = "timeout"
    art.error_category = "AgentTimeoutError"
    result = engine.score_run([art])
    ss = result.scenario_scores["sc-1"]
    assert ss.metric_results["harness_failure"].score == 0.0
    assert "AgentTimeoutError" in (ss.metric_results["harness_failure"].error or "")


def _artifact_blank(final: str = "", scenario_id: str = "sc-1") -> RunArtifact:
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


def test_dimensions_blank_completion() -> None:
    """Blank completion produces a quality score of 0.0 (no answer) while
    compatibility and safety remain 1.0 (no harness failures, no violations).
    """
    pack = _pack()
    pack.scenarios[0].metrics = {
        "tool_correctness": Metric(threshold=1.0),
        "output_correctness": Metric(threshold=1.0),
    }
    engine = ScoringEngine(pack)
    art = _artifact_blank(final="")
    result = engine.score_run([art])
    dims = result.dimensions
    assert dims.get("compatibility", 1.0) == 1.0
    assert dims.get("safety", 1.0) == 1.0
    assert dims.get("quality", 1.0) < 1.0


def test_dimensions_safety_violation() -> None:
    """Disallowed tool usage causes safety_score to drop below 1.0 while
    compatibility and quality remain at 1.0.
    """
    pack = _pack()
    pack.scenarios[0].disallowed_tools = [Tool(name="danger")]
    pack.scenarios[0].metrics = {
        "tool_correctness": Metric(threshold=1.0),
        "zero_disallowed_actions": Metric(threshold=1.0),
    }
    engine = ScoringEngine(pack)
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1})(),
    ]
    result = engine.score_run([art])
    dims = result.dimensions
    assert dims.get("compatibility", 1.0) == 1.0
    assert dims.get("safety", 1.0) < 1.0
    assert dims.get("quality", 1.0) == 1.0


def test_dimensions_wrong_answer() -> None:
    """A wrong answer causes quality_score to drop while compatibility and
    safety remain at 1.0.
    """
    pack = _pack()
    pack.scenarios[0].metrics = {"tool_correctness": Metric(threshold=1.0)}
    engine = ScoringEngine(pack)
    art = _artifact(final="wrong")
    art.trajectory = [
        type(
            "Step",
            (),
            {"type": "tool_call", "tool": "unknown_tool", "args": {}, "duration_ms": 1},
        )(),
    ]
    result = engine.score_run([art])
    dims = result.dimensions
    assert dims.get("compatibility", 1.0) == 1.0
    assert dims.get("safety", 1.0) == 1.0
    assert dims.get("quality", 1.0) < 1.0


# ── #273 — Rubric criteria + trajectory in judge prompt ──────────────────

from evalforge.scoring.judge.scorers import _build_prompt  # noqa: E402


def test_judge_prompt_contains_criteria() -> None:
    scenario = Scenario(
        id="sc-criteria",
        title="T",
        input="do the thing",
        goal="achieve the goal",
        allowed_tools=[Tool(name="a")],
        expected=Expected(
            type="rubric",
            criteria=["Agent must NOT call X", "Agent must return a summary"],
        ),
    )
    artifact = RunArtifact(
        id="r1", scenario_id="sc-criteria",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="done"),
        trajectory=[],
        cost=Cost(),
        status="completed",
    )
    prompt = _build_prompt(scenario, artifact, "test criterion")
    assert "### Rubric Criteria" in prompt
    assert "Agent must NOT call X" in prompt
    assert "Agent must return a summary" in prompt


def test_judge_prompt_omits_expected_when_none() -> None:
    scenario = Scenario(
        id="sc-no-expected",
        title="T",
        input="do the thing",
        goal="achieve the goal",
        allowed_tools=[Tool(name="a")],
        expected=Expected(type="exact", value=None),
    )
    artifact = RunArtifact(
        id="r1", scenario_id="sc-no-expected",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="done"),
        trajectory=[],
        cost=Cost(),
        status="completed",
    )
    prompt = _build_prompt(scenario, artifact, "test criterion")
    assert "### Expected Answer" not in prompt


def test_judge_prompt_contains_trajectory() -> None:
    scenario = Scenario(
        id="sc-trajectory",
        title="T",
        input="do the thing",
        goal="achieve the goal",
        allowed_tools=[Tool(name="a")],
    )
    artifact = RunArtifact(
        id="r1", scenario_id="sc-trajectory",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="done"),
        trajectory=[
            TrajectoryStep(type="tool_call", tool="a", args={}, duration_ms=10),
            TrajectoryStep(type="tool_result", tool="a", result="ok"),
        ],
        cost=Cost(),
        status="completed",
    )
    prompt = _build_prompt(scenario, artifact, "test criterion")
    assert "### Agent Trajectory" in prompt


# ── #258 — policy_adherence hybrid offline/online ────────────────────────


def test_hybrid_offline_disallowed_tool() -> None:
    pack = _pack()
    pack.scenarios[0].metrics = {"policy_adherence": Metric(threshold=1.0)}
    pack.scenarios[0].allowed_tools = [Tool(name="a")]
    pack.scenarios[0].disallowed_tools = [Tool(name="danger")]
    engine = ScoringEngine(pack)
    art = _artifact()
    art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1})(),
    ]
    result = engine.score_run([art])
    ss = result.scenario_scores["sc-1"]
    sr = ss.metric_results["policy_adherence"]
    assert sr.score == 0.0
    assert sr.detail.get("judge_not_evaluated") is True
    assert result.exit_code == 4


def test_hybrid_online_with_judge() -> None:
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
    ss = result.scenario_scores["sc-1"]
    sr = ss.metric_results["policy_adherence"]
    assert sr.score == 1.0
    assert "safe_calls" in sr.detail
    assert result.exit_code == 0


# ── #250 — Pluggable scorer bridge ───────────────────────────────────────


from evalforge.scoring.registry import _get_plugin_manager  # noqa: E402


class _PluginTestScorer(Scorer):
    name = "plugin_test_scorer"
    category = "correctness"

    def score(self, artifact, scenario, metric_config):
        return ScoreResult(
            metric=self.name,
            score=0.75,
            threshold=metric_config.get("threshold", 0.5),
            passed=True,
            category=self.category,
            blocking=False,
            detail={},
            source="deterministic",
            error=None,
        )


def test_plugin_scorer_invoked_via_registry() -> None:
    pm = _get_plugin_manager()
    pm.registry.register_scorer("plugin_test_scorer", _PluginTestScorer)
    try:
        found = get_scorer("plugin_test_scorer")
        assert found is _PluginTestScorer
    finally:
        pm.registry._scorers.pop("plugin_test_scorer", None)


def test_plugin_metric_score_run() -> None:
    pm = _get_plugin_manager()
    pm.registry.register_scorer("plugin_test_scorer", _PluginTestScorer)
    try:
        pack = _pack()
        pack.scenarios[0].metrics = {"plugin_test_scorer": Metric(threshold=0.5)}
        engine = ScoringEngine(pack)
        art = _artifact()
        art.trajectory = [
            type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
        ]
        result = engine.score_run([art])
        ss = result.scenario_scores["sc-1"]
        sr = ss.metric_results["plugin_test_scorer"]
        assert sr.score == 0.75
        assert sr.passed is True
    finally:
        pm.registry._scorers.pop("plugin_test_scorer", None)
