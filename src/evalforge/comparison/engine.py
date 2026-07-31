"""Comparison engine — candidate-vs-baseline delta computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evalforge.baselines.model import Baseline
from evalforge.models.pack import ScenarioPack
from evalforge.scoring.result import RunScore


@dataclass
class ComparisonResult:
    scenario_deltas: dict[str, dict[str, Any]]
    family_deltas: dict[str, dict[str, Any]]
    aggregate: dict[str, Any]


class ComparisonEngine:
    def __init__(self, pack: ScenarioPack) -> None:
        self._pack = pack
        self._scenario_map = {s.id: s for s in pack.scenarios}

    def compare(
        self,
        baseline_score: RunScore,
        candidate_score: RunScore,
        baseline: Baseline,
        candidate_artifacts: list[Any] | None = None,
    ) -> ComparisonResult:
        scenario_deltas: dict[str, dict[str, Any]] = {}
        family_scores: dict[str, list[float]] = {}
        candidate_family_scores: dict[str, list[float]] = {}

        all_ids = set(baseline_score.scenario_scores) | set(candidate_score.scenario_scores)
        for sid in all_ids:
            base_ss = baseline_score.scenario_scores.get(sid)
            cand_ss = candidate_score.scenario_scores.get(sid)
            base_score = self._scenario_avg(base_ss)
            cand_score = self._scenario_avg(cand_ss)
            delta = (cand_score or 0.0) - (base_score or 0.0)

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

            scenario = self._scenario_map.get(sid)
            if scenario and scenario.tags:
                for tag in scenario.tags:
                    if base_score is not None:
                        family_scores.setdefault(tag, []).append(base_score)
                    if cand_score is not None:
                        candidate_family_scores.setdefault(tag, []).append(cand_score)

        family_deltas: dict[str, dict[str, Any]] = {}
        for tag in set(family_scores) | set(candidate_family_scores):
            base_avg = _avg(family_scores.get(tag, []))
            cand_avg = _avg(candidate_family_scores.get(tag, []))
            family_deltas[tag] = {
                "baseline_avg": base_avg,
                "candidate_avg": cand_avg,
                "score_delta": cand_avg - base_avg,
            }

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

        # Cost delta: baseline runs vs candidate artifacts
        base_cost = _sum_cost(baseline.runs)
        cand_cost = _sum_cost(candidate_artifacts or [])
        cost_delta = round(cand_cost - base_cost, 6)

        aggregate = {
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
        if ss is None:
            return None
        scores = [
            r.score for r in getattr(ss, "metric_results", {}).values()
            if r.score is not None
        ]
        return _avg(scores) if scores else None


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sum_cost(artifacts: list[Any]) -> float:
    total = 0.0
    for a in artifacts:
        c = getattr(a, "cost", None)
        if c is not None:
            total += getattr(c, "cost_usd", 0.0) or 0.0
    return round(total, 6)
