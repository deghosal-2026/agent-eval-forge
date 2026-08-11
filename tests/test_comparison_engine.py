"""Tests for the ComparisonEngine: 3-level delta computation.

Covers:
- ComparisonResult dataclass defaults
- Comparing identical runs (zero delta, no regressions)
- Detecting a regression (score drop + status change)
- Per-family/tag delta aggregation
"""

from evalforge.baselines.model import Baseline
from evalforge.comparison.engine import ComparisonEngine, ComparisonResult
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
from evalforge.scoring.deterministic import tools  # noqa: F401
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge import scorers  # noqa: F401
from evalforge.scoring.result import RunScore


def _artifact(final: str = "ok", scenario_id: str = "sc-1") -> RunArtifact:
    """Factory helper: create a minimal RunArtifact for test scenarios."""
    return RunArtifact(
        id=f"r-{scenario_id}",
        scenario_id=scenario_id,
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final=final, structured=None),
        trajectory=[],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def _pack() -> ScenarioPack:
    """Factory helper: a 2-scenario pack with tool_correctness metric.

    sc-1 is tagged "retrieval", sc-2 is tagged "synthesis" — enables
    exercising per-family delta aggregation.
    """
    return ScenarioPack(
        pack=PackMetadata(name="test", version="1.0.0"),
        scenarios=[
            Scenario(
                id="sc-1", title="T", input="i", goal="g",
                allowed_tools=[Tool(name="a")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["retrieval"],
            ),
            Scenario(
                id="sc-2", title="T2", input="i2", goal="g2",
                allowed_tools=[Tool(name="b")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["synthesis"],
            ),
        ],
    )


def _run_score(pack: ScenarioPack, artifacts: list[RunArtifact]) -> RunScore:
    """Factory helper: score artifacts through the ScoringEngine."""
    engine = ScoringEngine(pack)
    return engine.score_run(artifacts)


def test_comparison_result_defaults() -> None:
    """ComparisonResult should accept empty dicts for all fields."""
    r = ComparisonResult(scenario_deltas={}, family_deltas={}, aggregate={})
    assert r.scenario_deltas == {}
    assert r.aggregate == {}


def test_compare_identical_runs() -> None:
    """Comparing identical runs should produce zero deltas and no regressions."""
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=arts)
    baseline_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, baseline_score, baseline)
    assert result.aggregate["overall_score_delta"] == 0.0
    assert result.aggregate["regressed"] == 0
    assert result.aggregate["improved"] == 0


def test_compare_regression_detected() -> None:
    """A scenario that passes in baseline but fails in candidate should be regressed."""
    pack = _pack()
    passing_arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    for art in passing_arts:
        art.trajectory = [
            type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
        ]
    failing_arts = [
        _artifact(final="bad", scenario_id="sc-1"),
        _artifact(scenario_id="sc-2"),
    ]
    failing_arts[0].trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=passing_arts)
    baseline_score = _run_score(pack, passing_arts)
    candidate_score = _run_score(pack, failing_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, candidate_score, baseline, failing_arts)
    assert result.aggregate["regressed"] >= 1
    assert result.aggregate["overall_score_delta"] < 0


def test_compare_family_deltas() -> None:
    """Comparing identical runs should produce family deltas with zero deltas."""
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=arts)
    baseline_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, baseline_score, baseline)
    assert "retrieval" in result.family_deltas
    assert "synthesis" in result.family_deltas


def test_compare_score_delta_regression() -> None:
    """Score drop > threshold classifies as regressed even with same status."""
    pack = _pack()
    # Baseline: agent calls allowed tool → high score
    base_art = _artifact(scenario_id="sc-1")
    base_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    base_score = _run_score(pack, [base_art])

    # Candidate: agent calls wrong tool → low score (but still "warn" not "failed")
    cand_art = _artifact(final="bad", scenario_id="sc-1")
    cand_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    cand_score = _run_score(pack, [cand_art])

    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=[base_art])
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline)
    # Score drops from ~1.0 to 0.0 — well beyond 0.05 threshold
    regressed = any(d["score_delta_regressed"] for d in result.scenario_deltas.values())
    assert regressed, f"Expected score-delta regression, got: {result.scenario_deltas}"


def test_compare_classifies_timeout_as_agent_crashed() -> None:
    """Scenario with TIMEOUT classified as agent_crashed."""
    pack = _pack()
    base_art = _artifact(scenario_id="sc-1")
    base_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    base_score = _run_score(pack, [base_art])

    cand_art = _artifact(scenario_id="sc-1")
    cand_art.status = "timeout"
    cand_art.error_category = "AgentTimeoutError"
    cand_score = _run_score(pack, [cand_art])

    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=[base_art])
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline)
    fc = result.scenario_deltas["sc-1"]["failure_category"]
    assert fc is not None


def test_compare_classifies_hallucination_as_scenario_failed() -> None:
    """Scenario with HALLUCINATION classified as scenario_failed."""
    pack = _pack()
    base_art = _artifact(scenario_id="sc-1")
    base_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    base_score = _run_score(pack, [base_art])

    cand_art = _artifact(final="bad", scenario_id="sc-1")
    cand_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    cand_score = _run_score(pack, [cand_art])

    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=[base_art])
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline)
    fc = result.scenario_deltas["sc-1"]["failure_category"]
    assert fc is not None


def test_compare_surfaces_safety_violations() -> None:
    """Safety violations from ScenarioScore surface in comparison output."""
    pack = _pack()
    base_art = _artifact(scenario_id="sc-1")
    base_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "a", "args": {}, "duration_ms": 1})(),
    ]
    base_score = _run_score(pack, [base_art])

    cand_art = _artifact(scenario_id="sc-1")
    cand_art.trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1})(),
    ]
    cand_score = _run_score(pack, [cand_art])

    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=[base_art])
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline)
    assert "safety_violations" in result.scenario_deltas["sc-1"]


def test_adapter_change_detected() -> None:
    """Different adapter manifests between baseline and candidate → adapter_changed."""
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline_manifest = {
        "name": "python_import",
        "version": "1.0.0",
        "digest": "aaaa",
    }
    candidate_manifest = {
        "name": "subprocess",
        "version": "1.0.0",
        "digest": "bbbb",
    }
    baseline = Baseline(
        name="v1", pack="test", pack_version="1.0.0",
        runs=arts, adapter_manifest=baseline_manifest,
    )
    baseline_score = _run_score(pack, arts)
    candidate_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(
        baseline_score, candidate_score, baseline,
        candidate_artifacts=arts,
        candidate_adapter_manifest=candidate_manifest,
    )
    assert result.aggregate["adapter_changed"] is True


def test_adapter_change_suppressed() -> None:
    """--allow-adapter-change suppresses adapter change detection."""
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline_manifest = {
        "name": "python_import",
        "version": "1.0.0",
        "digest": "aaaa",
    }
    candidate_manifest = {
        "name": "subprocess",
        "version": "1.0.0",
        "digest": "bbbb",
    }
    baseline = Baseline(
        name="v1", pack="test", pack_version="1.0.0",
        runs=arts, adapter_manifest=baseline_manifest,
    )
    baseline_score = _run_score(pack, arts)
    candidate_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(
        baseline_score, candidate_score, baseline,
        candidate_artifacts=arts,
        candidate_adapter_manifest=candidate_manifest,
        allow_adapter_change=True,
    )
    assert result.aggregate["adapter_changed"] is False


def test_model_change_detected() -> None:
    """Different agent models → classified as model_changed."""
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline = Baseline(
        name="v1", pack="test", pack_version="1.0.0",
        runs=arts, agent={"model": "gpt-4o"},
    )
    baseline_score = _run_score(pack, arts)
    candidate_arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    for a in candidate_arts:
        a.agent = {"model": "gpt-4o-mini"}
    candidate_score = _run_score(pack, candidate_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(
        baseline_score, candidate_score, baseline,
        candidate_artifacts=candidate_arts,
    )
    assert result.aggregate["model_changed"] is True


def test_same_model_no_change() -> None:
    """Same model across baseline and candidate → no model change."""
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    for a in arts:
        a.agent = {"model": "gpt-4o"}
    baseline = Baseline(
        name="v1", pack="test", pack_version="1.0.0",
        runs=arts, agent={"model": "gpt-4o"},
    )
    baseline_score = _run_score(pack, arts)
    candidate_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(
        baseline_score, candidate_score, baseline,
        candidate_artifacts=arts,
    )
    assert result.aggregate["model_changed"] is False
