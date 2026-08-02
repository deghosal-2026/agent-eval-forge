"""``evalforge compare`` — compare a candidate run against a golden baseline.

Loads a candidate run (from a saved run directory) and a saved baseline,
re-scores the baseline's artifacts through the ScoringEngine, computes
per-scenario, per-family, and aggregate deltas, and produces a report.

Supports three output formats: JSON (machine-readable, CI-friendly),
Markdown (human-readable, PR-comment-ready), and terminal (Rich table).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click


@click.command()
@click.option(
    "--candidate",
    required=True,
    help="Path to the candidate run directory (e.g. .evalforge/runs/run-20260728-120000-abc123)",
)
@click.option("--baseline", required=True, help="Name of the saved baseline to compare against")
@click.option(
    "--pack",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Scenario pack used for both the baseline and candidate runs",
)
@click.option(
    "--output-dir",
    default=".evalforge",
    show_default=True,
    help="Output directory where baselines are stored",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "markdown", "terminal"]),
    default="terminal",
    show_default=True,
)
def compare(
    candidate: str,
    baseline: str,
    pack: str,
    output_dir: str,
    output_format: str,
) -> None:
    """Compare a candidate run against a golden baseline.

    The comparison computes deltas at three levels:
    1. Per-scenario: did each individual scenario regress or improve?
    2. Per-family: grouped by scenario tags (e.g., all "retrieval" scenarios).
    3. Aggregate: overall score delta, cost delta, and scenario counts.

    The output report highlights regressions, improvements, new failures,
    new passes, and safety violations.

    Args:
        candidate: Path to the candidate run directory containing scores.json
            or per-scenario artifact JSONs.
        baseline: Name of the saved baseline to compare against.
        pack: Path to the scenario pack used for both runs.
        output_dir: Base output directory where baselines are stored.
        output_format: Output rendering format.

    Exits with:
        0 on success, 1 if the candidate run directory is not found or
        the baseline is missing.
    """
    # Core imports deferred for fast --help
    from evalforge.baselines.store import BaselineStore
    from evalforge.cli.formatter import OutputFormatter
    from evalforge.comparison.engine import ComparisonEngine
    from evalforge.comparison.report import ComparisonReport
    from evalforge.loading.pack_loader import load_pack
    from evalforge.models.artifact import RunArtifact
    from evalforge.scoring.engine import ScoringEngine

    # Load the scenario pack — shared schema for both baseline and candidate
    scenario_pack = load_pack(pack)

    # Verify candidate run directory exists
    run_dir = Path(candidate)
    if not run_dir.exists():
        click.echo(f"Error: candidate run directory not found: {candidate}", err=True)
        raise SystemExit(1)

    # Load candidate scores either from saved scores.json or by re-scoring artifacts
    scores_json = run_dir / "scores.json"
    if scores_json.exists():
        data = json.loads(scores_json.read_text())
        candidate_score = _runscore_from_dict(data)
    else:
        # Fall back to re-scoring raw artifacts from the candidate run
        artifact_dir = run_dir / "artifacts"
        artifacts: list[RunArtifact] = []
        if artifact_dir.exists():
            for af in sorted(artifact_dir.glob("*.json")):
                artifacts.append(RunArtifact(**json.loads(af.read_text())))
        engine = ScoringEngine(scenario_pack)
        candidate_score = engine.score_run(artifacts)

    # Load the baseline from the baseline store
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    try:
        baseline_obj = store.load(baseline)
    except FileNotFoundError:
        click.echo(f"Error: baseline '{baseline}' not found", err=True)
        raise SystemExit(1) from None

    # Re-score the baseline's artifacts to produce a RunScore for comparison
    engine = ScoringEngine(scenario_pack)
    baseline_score = engine.score_run(baseline_obj.runs)

    # Compute three-level deltas
    comp_engine = ComparisonEngine(scenario_pack)
    comp_result = comp_engine.compare(
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        baseline=baseline_obj,
    )

    # Build and output the comparison report
    report = ComparisonReport(
        baseline_name=baseline,
        candidate_name=Path(candidate).name,
        result=comp_result,
        candidate_score=candidate_score,
    )

    formatter = OutputFormatter(output_format)
    formatter.format_comparison(report, output_path=f"{candidate}/comparison.md")


def _runscore_from_dict(data: dict[str, Any]) -> Any:
    """Reconstruct a ``RunScore`` from a serialized JSON dictionary.

    This is the inverse of the serialization performed in ``run.py`` when
    it writes ``scores.json``. It reconstructs all nested ``ScoreResult``
    and ``ScenarioScore`` objects so they can be fed to the
    ``ComparisonEngine``.

    Args:
        data: A dictionary previously produced by ``run.py``'s result payload.

    Returns:
        A fully hydrated ``RunScore`` with per-scenario metric results.
    """
    from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult

    scenario_scores: dict[str, ScenarioScore] = {}
    for sid, sd in data.get("scenario_scores", {}).items():
        metric_results: dict[str, ScoreResult] = {}
        for mn, mr in sd.get("metrics", {}).items():
            metric_results[mn] = ScoreResult(
                metric=mn,
                score=mr.get("score"),
                threshold=mr.get("threshold"),
                passed=mr.get("passed"),
                category=mr.get("category", "correctness"),
                blocking=mr.get("blocking", False),
                detail=mr.get("detail", {}),
                source=mr.get("source", "deterministic"),
                error=mr.get("error"),
            )
        scenario_scores[sid] = ScenarioScore(
            scenario_id=sid,
            metric_results=metric_results,
            status=sd.get("status", "failed"),
            safety_violations=sd.get("safety_violations", []),
        )
    return RunScore(
        scenario_scores=scenario_scores,
        totals=data.get("totals", {"passed": 0, "warned": 0, "failed": 0}),
        safety_violations=data.get("safety_violations", []),
        exit_code=data.get("exit_code", 1),
    )
