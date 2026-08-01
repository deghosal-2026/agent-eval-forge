"""Tests for ComparisonReport: JSON and Markdown output generation.

Covers:
- JSON output structure and field presence
- Markdown output includes baseline/candidate names, summary, and scenario info
- Safety violations appear prominently in the markdown output
"""

from evalforge.comparison.engine import ComparisonResult
from evalforge.comparison.report import ComparisonReport
from evalforge.scoring.result import RunScore


def _make_result() -> ComparisonResult:
    """Factory helper: a ComparisonResult with one regression and one improvement."""
    return ComparisonResult(
        scenario_deltas={
            "sc-1": {
                "baseline_score": 1.0, "candidate_score": 0.5, "delta": -0.5,
                "baseline_status": "passed", "candidate_status": "failed",
                "regressed": True, "improved": False,
                "new_failure": False, "new_pass": False,
            },
            "sc-2": {
                "baseline_score": 0.0, "candidate_score": 1.0, "delta": 1.0,
                "baseline_status": "failed", "candidate_status": "passed",
                "regressed": False, "improved": True,
                "new_failure": False, "new_pass": False,
            },
        },
        family_deltas={
            "retrieval": {"baseline_avg": 1.0, "candidate_avg": 0.5, "score_delta": -0.5},
        },
        aggregate={
            "total_scenarios": 2, "regressed": 1, "improved": 1,
            "new_failures": 0, "new_passes": 0, "unchanged": 0,
            "overall_score_delta": 0.25,
        },
    )


def _run_score() -> RunScore:
    """Factory helper: a RunScore with no safety violations, exit code 1."""
    return RunScore(
        scenario_scores={},
        totals={"passed": 1, "warned": 0, "failed": 1},
        safety_violations=[],
        exit_code=1,
    )


def test_report_to_json() -> None:
    """JSON output should include baseline/candidate names, aggregates, and deltas."""
    report = ComparisonReport(
        baseline_name="v1.0.0",
        candidate_name="v1.1.0",
        result=_make_result(),
        candidate_score=_run_score(),
    )
    data = report.to_json()
    assert data["baseline_name"] == "v1.0.0"
    assert data["candidate_name"] == "v1.1.0"
    assert data["aggregate"]["regressed"] == 1
    assert "sc-1" in data["scenario_deltas"]
    assert "retrieval" in data["family_deltas"]


def test_report_to_markdown() -> None:
    """Markdown output should contain identifying info, summary, and scenario data."""
    report = ComparisonReport(
        baseline_name="v1.0.0",
        candidate_name="v1.1.0",
        result=_make_result(),
        candidate_score=_run_score(),
    )
    md = report.to_markdown()
    assert "v1.0.0" in md
    assert "v1.1.0" in md
    assert "Summary" in md
    assert "sc-1" in md
    assert "regressed" in md.lower()


def test_report_markdown_contains_safety_violations() -> None:
    """Markdown should prominently display safety violations when present."""
    score = RunScore(
        scenario_scores={},
        totals={"passed": 0, "warned": 0, "failed": 1},
        safety_violations=["zero_disallowed_actions"],
        exit_code=4,
    )
    report = ComparisonReport(
        baseline_name="v1", candidate_name="v2",
        result=_make_result(), candidate_score=score,
    )
    md = report.to_markdown()
    assert "SAFETY" in md.upper() or "exit code 4" in md
