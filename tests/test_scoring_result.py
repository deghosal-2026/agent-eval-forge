"""Tests for scoring result models and error types."""

from evalforge.models.errors import ConfigError, EvalForgeError, JudgeError
from evalforge.scoring.result import JudgeVerdict, RunScore, ScenarioScore, ScoreResult


def test_config_error_is_evalforge_error() -> None:
    err = ConfigError("bad config")
    assert isinstance(err, EvalForgeError)
    assert str(err) == "bad config"


def test_judge_error_is_evalforge_error() -> None:
    err = JudgeError("judge unavailable")
    assert isinstance(err, EvalForgeError)
    assert str(err) == "judge unavailable"


def test_score_result_defaults() -> None:
    r = ScoreResult(
        metric="tool_correctness",
        score=0.5,
        threshold=0.8,
        passed=False,
        category="correctness",
        blocking=False,
        detail={"expected": 2, "actual": 1},
        source="deterministic",
        error=None,
    )
    assert r.metric == "tool_correctness"
    assert r.score == 0.5
    assert r.passed is False
    assert r.blocking is False
    assert r.error is None


def test_score_result_error() -> None:
    r = ScoreResult(
        metric="task_completion",
        score=None,
        threshold=0.8,
        passed=None,
        category="correctness",
        blocking=False,
        detail={},
        source="judge",
        error="judge not configured",
    )
    assert r.score is None
    assert r.passed is None
    assert r.error == "judge not configured"


def test_scenario_score() -> None:
    r = ScoreResult(
        metric="t",
        score=1.0,
        threshold=0.8,
        passed=True,
        category="correctness",
        blocking=False,
        detail={},
        source="deterministic",
        error=None,
    )
    ss = ScenarioScore(
        scenario_id="sc-1", metric_results={"t": r}, status="passed", safety_violations=[]
    )
    assert ss.scenario_id == "sc-1"
    assert ss.status == "passed"
    assert ss.safety_violations == []


def test_run_score() -> None:
    rs = RunScore(
        scenario_scores={},
        totals={"passed": 0, "warned": 0, "failed": 0},
        safety_violations=[],
        exit_code=0,
    )
    assert rs.exit_code == 0
    assert rs.totals["passed"] == 0


def test_judge_verdict() -> None:
    v = JudgeVerdict(score=0.85, rationale="Good answer")
    assert v.score == 0.85
    assert v.rationale == "Good answer"
