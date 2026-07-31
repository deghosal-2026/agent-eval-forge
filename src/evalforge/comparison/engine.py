"""Comparison engine: candidate-vs-baseline deltas and reports (spec §"Comparison Model").

Compares a candidate run's scores against a golden baseline at three levels:

1. Per-scenario delta — how did each individual scenario change?
2. Per-family/tag delta — did a class of scenarios (e.g. "retrieval") regress?
3. Aggregate pack delta — what's the overall score change?

Also computes cost deltas (baseline runs vs candidate artifacts) so teams
can track whether the agent became more or less expensive.

Usage:
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, candidate_score, baseline)
    print(result.aggregate["regressed"])  # number of regressed scenarios
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evalforge.baselines.model import Baseline
from evalforge.models.pack import ScenarioPack
from evalforge.scoring.result import RunScore


@dataclass
class ComparisonResult:
    """The output of a single comparison operation.

    Attributes:
        scenario_deltas: Mapping of scenario_id -> delta dict with keys:
            baseline_score, candidate_score, delta, baseline_status,
            candidate_status, regressed, improved, new_failure, new_pass.
        family_deltas: Mapping of tag/family -> delta dict with keys:
            baseline_avg, candidate_avg, score_delta.
        aggregate: Top-level summary with keys: total_scenarios, regressed,
            improved, new_failures, new_passes, unchanged,
            overall_score_delta, cost_delta_usd, baseline_cost_usd,
            candidate_cost_usd.
    """

    scenario_deltas: dict[str, dict[str, Any]]
    family_deltas: dict[str, dict[str, Any]]
    aggregate: dict[str, Any]


class ComparisonEngine:
    """Computes deltas between a baseline run score and a candidate run score.

    The engine is initialized with the ScenarioPack so it can resolve
    scenario metadata (tags, families) for the per-family aggregation.
    """

    def __init__(self, pack: ScenarioPack) -> None:
        """Initialize with the scenario pack to compare against.

        Args:
            pack: The ScenarioPack containing the scenario definitions.
                Used to resolve scenario tags for per-family aggregation.
        """
        self._pack = pack
        self._scenario_map = {s.id: s for s in pack.scenarios}

    def compare(
        self,
        baseline_score: RunScore,
        candidate_score: RunScore,
        baseline: Baseline,
        candidate_artifacts: list[Any] | None = None,
    ) -> ComparisonResult:
        """Compare a candidate run score against a baseline.

        Produces three levels of deltas:
        1. Per-scenario: each scenario's score, status, and whether it
           regressed, improved, or is new.
        2. Per-family: aggregate deltas grouped by scenario tag.
        3. Aggregate: top-level counts and overall score delta.

        Args:
            baseline_score: The RunScore from the baseline run.
            candidate_score: The RunScore from the candidate run.
            baseline: The Baseline object (used for cost data from its runs).
            candidate_artifacts: The candidate's RunArtifacts (used for
                cost delta computation). Optional — cost delta is 0 if omitted.

        Returns:
            A ComparisonResult with deltas at all three levels.
        """
        scenario_deltas: dict[str, dict[str, Any]] = {}
        family_scores: dict[str, list[float]] = {}
        candidate_family_scores: dict[str, list[float]] = {}

        # Iterate over the union of all scenario IDs from both scores
        all_ids = set(baseline_score.scenario_scores) | set(candidate_score.scenario_scores)
        for sid in all_ids:
            base_ss = baseline_score.scenario_scores.get(sid)
            cand_ss = candidate_score.scenario_scores.get(sid)
            base_score = self._scenario_avg(base_ss)
            cand_score = self._scenario_avg(cand_ss)
            delta = (cand_score or 0.0) - (base_score or 0.0)

            # Classify the scenario change
            scenario_deltas[sid] = {
                "baseline_score": base_score,
                "candidate_score": cand_score,
                "delta": delta,
                "baseline_status": base_ss.status if base_ss else None,
                "candidate_status": cand_ss.status if cand_ss else None,
                "regressed": (
                    base_ss is not None and cand_ss is not None
                    and base_ss.status == "passed" and cand_ss.status != "passed"
                ),
                "improved": (
                    base_ss is not None and cand_ss is not None
                    and base_ss.status != "passed" and cand_ss.status == "passed"
                ),
                "new_failure": (
                    base_ss is None and cand_ss is not None and cand_ss.status != "passed"
                ),
                "new_pass": base_ss is None and cand_ss is not None and cand_ss.status == "passed",
            }

            # Accumulate scores per family/tag for per-family aggregation
            scenario = self._scenario_map.get(sid)
            if scenario and scenario.tags:
                for tag in scenario.tags:
                    if base_score is not None:
                        family_scores.setdefault(tag, []).append(base_score)
                    if cand_score is not None:
                        candidate_family_scores.setdefault(tag, []).append(cand_score)

        # Per-family aggregation
        family_deltas: dict[str, dict[str, Any]] = {}
        for tag in set(family_scores) | set(candidate_family_scores):
            base_avg = _avg(family_scores.get(tag, []))
            cand_avg = _avg(candidate_family_scores.get(tag, []))
            family_deltas[tag] = {
                "baseline_avg": base_avg,
                "candidate_avg": cand_avg,
                "score_delta": cand_avg - base_avg,
            }

        # Aggregate counts
        regressed = sum(1 for d in scenario_deltas.values() if d["regressed"])
        improved = sum(1 for d in scenario_deltas.values() if d["improved"])
        new_failures = sum(1 for d in scenario_deltas.values() if d["new_failure"])
        new_passes = sum(1 for d in scenario_deltas.values() if d["new_pass"])
        unchanged = sum(
            1 for d in scenario_deltas.values()
            if not d["regressed"] and not d["improved"]
            and not d["new_failure"] and not d["new_pass"]
        )
        overall_delta = _avg([
            d["delta"] for d in scenario_deltas.values()
            if d["delta"] is not None
        ])

        # Cost delta: compare total USD cost of baseline runs vs candidate
        base_cost = _sum_cost(baseline.runs)
        cand_cost = _sum_cost(candidate_artifacts or [])
        cost_delta = round(cand_cost - base_cost, 6)

        aggregate: dict[str, Any] = {
            "total_scenarios": len(scenario_deltas),
            "regressed": regressed,
            "improved": improved,
            "new_failures": new_failures,
            "new_passes": new_passes,
            "unchanged": unchanged,
            "overall_score_delta": overall_delta,
            "cost_delta_usd": cost_delta,
            "baseline_cost_usd": base_cost,
            "candidate_cost_usd": cand_cost,
        }

        return ComparisonResult(
            scenario_deltas=scenario_deltas,
            family_deltas=family_deltas,
            aggregate=aggregate,
        )

    @staticmethod
    def _scenario_avg(
        ss: object,
    ) -> float | None:
        """Compute the average score across all metrics in a ScenarioScore.

        Args:
            ss: A ScenarioScore object (typed as object to avoid import
                coupling with the scoring result module at import time).

        Returns:
            The average of all non-None metric scores, or None if no
            scores are available.
        """
        if ss is None:
            return None
        scores = [
            r.score for r in getattr(ss, "metric_results", {}).values()
            if r.score is not None
        ]
        return _avg(scores) if scores else None


def _avg(values: list[float]) -> float:
    """Compute the arithmetic mean of a list of floats.

    Returns 0.0 for empty lists to avoid division by zero.
    """
    return sum(values) / len(values) if values else 0.0


def _sum_cost(artifacts: list[Any]) -> float:
    """Sum the cost_usd field across a list of artifacts.

    Safely handles artifacts that may not have a cost field (e.g., the
    item is a dict or lacks the attribute) by using getattr with defaults.
    """
    total = 0.0
    for a in artifacts:
        c = getattr(a, "cost", None)
        if c is not None:
            total += getattr(c, "cost_usd", 0.0) or 0.0
    return round(total, 6)
