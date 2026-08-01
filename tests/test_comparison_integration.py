"""End-to-end integration tests for the full M3 pipeline: Baseline → Comparison → Report.

Covers the complete flow:
1. Create artifacts, score them, save as a Baseline
2. Load the baseline from the BaselineStore
3. Create candidate artifacts (with intentional regression), score them
4. Compare candidate vs baseline via ComparisonEngine
5. Generate JSON and Markdown reports via ComparisonReport
6. Verify all aggregate stats, deltas, and report content

Two scenarios verified:
- Regression path: one scenario fails in candidate that passed in baseline
- No-regression path: identical runs produce zero deltas
"""

from pathlib import Path

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
from evalforge.comparison.engine import ComparisonEngine
from evalforge.comparison.report import ComparisonReport
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
from evalforge.scoring.deterministic import (  # noqa: F401
    gates,
    tools,
)
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult
from evalforge.scoring.judge import scorers  # noqa: F401


def _pack() -> ScenarioPack:
    """Factory helper: a 2-scenario pack with tool_correctness metric."""
    return ScenarioPack(
        pack=PackMetadata(name="test-pack", version="1.0.0"),
        scenarios=[
            Scenario(
                id="sc-1", title="T1", input="i1", goal="g1",
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


def _artifact(final: str = "ok", sid: str = "sc-1") -> RunArtifact:
    """Factory helper: create a minimal RunArtifact for test scenarios."""
    return RunArtifact(
        id=f"r-{sid}", scenario_id=sid,
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final=final, structured=None),
        trajectory=[], cost=Cost(), status="completed", error=None, agent={},
    )


def test_end_to_end_baseline_save_compare_report(tmp_path: Path) -> None:
    """Full pipeline: save baseline, compare with regression, verify report output.

    Regression path:
    - sc-1 passes baseline, fails candidate (unknown tool called)
    - sc-2 passes both
    - Expected: >=1 regression, negative score delta, cost delta present
    """
    pack = _pack()
    base_dir = str(tmp_path / ".evalforge")
    store = BaselineStore(base_dir=f"{base_dir}/baselines")

    # Create and save baseline from passing artifacts
    base_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    base_score = ScoringEngine(pack).score_run(base_arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts)
    store.save(baseline)

    # Verify baseline loads correctly from disk
    loaded = store.load("v1.0")
    assert len(loaded.runs) == 2

    # Create candidate with a regression in sc-1
    cand_arts = [
        _artifact(final="bad", sid="sc-1"),
        _artifact(sid="sc-2"),
    ]
    cand_arts[0].trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, loaded, candidate_artifacts=cand_arts)

    assert result.aggregate["regressed"] >= 1
    assert result.aggregate["overall_score_delta"] < 0
    assert "cost_delta_usd" in result.aggregate

    # Generate and verify JSON report
    report = ComparisonReport(
        baseline_name="v1.0",
        candidate_name="candidate",
        result=result,
        candidate_score=cand_score,
    )
    json_output = report.to_json()
    assert json_output["aggregate"]["regressed"] >= 1

    # Generate and verify Markdown report
    md_output = report.to_markdown()
    assert "v1.0" in md_output
    assert "sc-1" in md_output
    assert "regressed" in md_output.lower()


def test_end_to_end_all_pass_no_regression(tmp_path: Path) -> None:
    """Full pipeline: identical runs produce zero regressions, zero deltas."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    score = ScoringEngine(pack).score_run(arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=arts)
    store.save(baseline)

    engine = ComparisonEngine(pack)
    result = engine.compare(score, score, baseline)
    assert result.aggregate["regressed"] == 0
    assert result.aggregate["improved"] == 0
    assert result.aggregate["overall_score_delta"] == 0.0


def test_baseline_save_list_load(tmp_path: Path) -> None:
    """Save a baseline, list all baselines, load by name, verify round-trip."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=arts)
    store.save(baseline)

    names = store.list()
    assert names == ["v1.0"]

    loaded = store.load("v1.0")
    assert loaded.name == "v1.0"
    assert loaded.pack == "test-pack"
    assert loaded.pack_version == "1.0.0"
    assert len(loaded.runs) == 2


def test_baseline_validate_version_check(tmp_path: Path) -> None:
    """Save baseline with one pack version, validate with different version, verify mismatch warning."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=arts)
    store.save(baseline)

    warning = store.validate("v1.0", pack_version="2.0.0")
    assert "version mismatch" in warning
    assert "1.0.0" in warning
    assert "2.0.0" in warning

    ok = store.validate("v1.0", pack_version="1.0.0")
    assert ok == ""


def test_comparison_detects_new_failures(tmp_path: Path) -> None:
    """Baseline has 2 passing scenarios, candidate has 1 failure -> 1 regression, score delta < 0."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    base_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    base_score = ScoringEngine(pack).score_run(base_arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts)
    store.save(baseline)

    cand_arts = [
        _artifact(sid="sc-1"),
        _artifact(sid="sc-2"),
    ]
    cand_arts[0].trajectory = [
        TrajectoryStep(type="tool_call", tool="unknown", args={}, duration_ms=1),
    ]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline, candidate_artifacts=cand_arts)

    assert result.aggregate["regressed"] == 1
    assert result.aggregate["improved"] == 0
    assert result.aggregate["total_scenarios"] == 2
    assert result.aggregate["overall_score_delta"] < 0
    assert result.scenario_deltas["sc-1"]["regressed"] is True
    assert result.scenario_deltas["sc-2"]["regressed"] is False


def test_comparison_detects_improvements(tmp_path: Path) -> None:
    """Baseline has 1 failure, candidate fixes it -> 1 improvement, score delta > 0."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    base_arts = [
        _artifact(sid="sc-1"),
        _artifact(sid="sc-2"),
    ]
    base_arts[0].trajectory = [
        TrajectoryStep(type="tool_call", tool="unknown", args={}, duration_ms=1),
    ]
    base_score = ScoringEngine(pack).score_run(base_arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts)
    store.save(baseline)

    cand_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline, candidate_artifacts=cand_arts)

    assert result.aggregate["improved"] == 1
    assert result.aggregate["regressed"] == 0
    assert result.aggregate["overall_score_delta"] > 0
    assert result.scenario_deltas["sc-1"]["improved"] is True


def test_comparison_snapshot_mode(tmp_path: Path) -> None:
    """Compare using snapshot mode (pre-computed scores) vs rescore mode produces same result."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    base_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    rescore = ScoringEngine(pack).score_run(base_arts)

    snapshot_dict: dict[str, dict[str, object]] = {
        sid: {
            "status": ss.status,
            "metric_results": {
                m: {
                    "metric": m,
                    "score": r.score,
                    "passed": r.passed,
                    "threshold": r.threshold,
                    "category": r.category,
                    "blocking": r.blocking,
                    "source": r.source,
                    "error": r.error,
                    "detail": {},
                }
                for m, r in ss.metric_results.items()
            },
        }
        for sid, ss in rescore.scenario_scores.items()
    }
    baseline = Baseline(
        name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts,
        score_snapshot=snapshot_dict,
    )
    store.save(baseline)

    loaded = store.load("v1.0")
    assert loaded.score_snapshot is not None
    snap_scores: dict[str, ScenarioScore] = {}
    for sid, data in loaded.score_snapshot.items():
        metric_results = {}
        for m, rd in data["metric_results"].items():
            metric_results[m] = ScoreResult(
                metric=rd["metric"], score=rd["score"], threshold=rd["threshold"],
                passed=rd["passed"], category=rd["category"], blocking=rd["blocking"],
                detail=rd["detail"], source=rd["source"], error=rd["error"],
            )
        snap_scores[sid] = ScenarioScore(
            scenario_id=sid, metric_results=metric_results, status=data["status"],
            safety_violations=[],
        )
    snapshot_score = RunScore(
        scenario_scores=snap_scores,
        totals=rescore.totals,
        safety_violations=rescore.safety_violations,
        exit_code=rescore.exit_code,
    )

    cand_arts = [_artifact(final="bad", sid="sc-1"), _artifact(sid="sc-2")]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)

    result_snapshot = engine.compare(snapshot_score, cand_score, baseline, candidate_artifacts=cand_arts)
    result_rescore = engine.compare(rescore, cand_score, baseline, candidate_artifacts=cand_arts)

    assert result_snapshot.aggregate == result_rescore.aggregate
    assert result_snapshot.scenario_deltas == result_rescore.scenario_deltas
    assert result_snapshot.family_deltas == result_rescore.family_deltas


def test_comparison_report_markdown_output(tmp_path: Path) -> None:
    """Verify markdown report has expected sections (pass/fail totals, per-scenario, per-family, aggregate delta)."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    base_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    base_score = ScoringEngine(pack).score_run(base_arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts)
    store.save(baseline)

    cand_arts = [_artifact(final="bad", sid="sc-1"), _artifact(sid="sc-2")]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline, candidate_artifacts=cand_arts)

    report = ComparisonReport(
        baseline_name="v1.0", candidate_name="candidate",
        result=result, candidate_score=cand_score,
    )
    md = report.to_markdown()

    assert "# Comparison Report: v1.0 \u2192 candidate" in md
    assert "## Summary" in md
    assert "## Per-Scenario Deltas" in md
    assert "## Per-Family Deltas" in md
    assert "sc-1" in md
    assert "sc-2" in md
    assert "retrieval" in md or "synthesis" in md
    assert "Total Scenarios" in md
    assert "Regressed" in md
    assert "Improved" in md
    assert "New Failures" in md
    assert "Overall Score Delta" in md
    assert "Cost Delta" in md


def test_comparison_report_json_output(tmp_path: Path) -> None:
    """Verify JSON report has correct structure with all required keys."""
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    base_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    base_score = ScoringEngine(pack).score_run(base_arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts)
    store.save(baseline)

    cand_arts = [_artifact(final="bad", sid="sc-1"), _artifact(sid="sc-2")]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, baseline, candidate_artifacts=cand_arts)

    report = ComparisonReport(
        baseline_name="v1.0", candidate_name="candidate",
        result=result, candidate_score=cand_score,
    )
    j = report.to_json()

    assert j["baseline_name"] == "v1.0"
    assert j["candidate_name"] == "candidate"
    assert "aggregate" in j
    assert "scenario_deltas" in j
    assert "family_deltas" in j

    agg = j["aggregate"]
    for key in (
        "total_scenarios", "regressed", "improved", "new_failures",
        "new_passes", "unchanged", "overall_score_delta",
        "candidate_totals", "candidate_exit_code", "safety_violations",
        "cost_delta_usd",
    ):
        assert key in agg, f"missing aggregate key: {key}"

    assert len(j["scenario_deltas"]) == 2
    assert "sc-1" in j["scenario_deltas"]
    assert "sc-2" in j["scenario_deltas"]
    for sid, delta in j["scenario_deltas"].items():
        for key in ("baseline_score", "candidate_score", "delta", "regressed", "improved"):
            assert key in delta, f"missing key {key} in scenario_delta[{sid}]"
