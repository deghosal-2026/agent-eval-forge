"""Reproducibility checker — measures score and trajectory variance across runs.

Compares multiple evaluation runs of the same scenario pack and reports
inconsistencies, recommending fixes when variance is detected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReproducibilityReport:
    """Report from a reproducibility check.

    Attributes:
        seed: Seed used for the check (may be 0 if not applicable).
        runs: Number of runs analysed.
        consistent_scores: Whether all scores were identical across runs.
        score_variance: Per-scenario max-min score delta.
        trajectory_variance: Per-scenario max-min trajectory length delta.
        recommendations: Human-readable suggestions for improving reproducibility.
    """
    seed: int
    runs: int
    consistent_scores: bool
    score_variance: dict[str, float] = field(default_factory=dict)
    trajectory_variance: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class ReproducibilityChecker:
    """Compares multiple evaluation runs to detect non-determinism."""

    def check(
        self,
        runner_results: list[Any],
    ) -> ReproducibilityReport:
        """Analyse a list of runner results for score and trajectory variance.

        Each result object must have a ``scenario_scores`` dict mapping
        scenario IDs to objects with a ``metric_results`` dict. Each
        metric result is expected to have a ``score`` attribute.

        Args:
            runner_results: List of run-score objects (e.g. ``RunScore``).

        Returns:
            A :class:`ReproducibilityReport` summarising findings.
        """
        if len(runner_results) < 2:
            return ReproducibilityReport(
                seed=0,
                runs=len(runner_results),
                consistent_scores=True,
                recommendations=["need at least 2 runs to check reproducibility"],
            )

        all_scenario_ids: set[str] = set()
        per_run_scores: list[dict[str, float]] = []
        per_run_trajectories: list[dict[str, int]] = []

        for run_score in runner_results:
            run_scores: dict[str, float] = {}
            run_traj: dict[str, int] = {}
            for sid, ss in run_score.scenario_scores.items():
                all_scenario_ids.add(sid)
                total = 0.0
                for mr in ss.metric_results.values():
                    if mr.score is not None:
                        total += mr.score
                run_scores[sid] = total
                run_traj[sid] = len(ss.metric_results)
            per_run_scores.append(run_scores)
            per_run_trajectories.append(run_traj)

        score_variance: dict[str, float] = {}
        trajectory_variance: dict[str, float] = {}
        for sid in all_scenario_ids:
            scores = [rs.get(sid, 0.0) for rs in per_run_scores]
            trajs = [rt.get(sid, 0) for rt in per_run_trajectories]
            score_variance[sid] = max(scores) - min(scores) if scores else 0.0
            trajectory_variance[sid] = float(max(trajs) - min(trajs)) if trajs else 0.0

        max_score_var = max(score_variance.values()) if score_variance else 0.0
        max_traj_var = max(trajectory_variance.values()) if trajectory_variance else 0.0
        consistent = max_score_var == 0.0 and max_traj_var == 0.0

        recommendations: list[str] = []
        if not consistent:
            if max_score_var > 0.0:
                recommendations.append(
                    f"Score variance detected (max delta: {max_score_var:.4f}). "
                    "Consider using SeedManager.set_global_seed() or EnvironmentFreezer."
                )
            if max_traj_var > 0.0:
                recommendations.append(
                    f"Trajectory variance detected (max delta: {max_traj_var:.0f}). "
                    "Ensure deterministic execution environment."
                )

        return ReproducibilityReport(
            seed=0,
            runs=len(runner_results),
            consistent_scores=consistent,
            score_variance=score_variance,
            trajectory_variance=trajectory_variance,
            recommendations=recommendations,
        )

    def check_single(
        self,
        pack_path: str,
        agent_spec: str,
        runs: int = 3,
    ) -> ReproducibilityReport:
        """Convenience: run a scenario pack multiple times and check reproducibility.

        Uses a mock agent via ``Runner`` and ``ScoringEngine``.

        Args:
            pack_path: Path to the scenario pack file.
            agent_spec: Agent specification string.
            runs: Number of times to repeat (default 3).

        Returns:
            A :class:`ReproducibilityReport`.
        """
        from evalforge.runner import Runner
        from evalforge.scoring.engine import ScoringEngine

        collected: list[Any] = []
        runner = Runner(agent_config={"type": "mock"})
        runner.load_pack(pack_path)

        for _ in range(runs):
            artifacts = runner.run_all()
            engine = ScoringEngine(runner.pack)
            run_score = engine.score_run(artifacts)
            collected.append(run_score)

        return self.check(collected)
