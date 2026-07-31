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

import pytest

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
from evalforge.comparison.engine import ComparisonEngine
from evalforge.comparison.report import ComparisonReport
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
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.deterministic import (  # noqa: F401
    gates, tools,
)
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