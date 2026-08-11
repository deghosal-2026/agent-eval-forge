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

from evalforge.analytics.taxonomy import FailureTaxonomy
from evalforge.baselines.model import Baseline
from evalforge.models.pack import ScenarioPack
from evalforge.scoring.result import RunScore, ScenarioScore

SCORE_DELTA_THRESHOLD = 0.05


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
            candidate_cost_usd, adapter_changed, model_changed.
    """

    scenario_deltas: dict[str, dict[str, Any]]
    family_deltas: dict[str, dict[str, Any]]
    aggregate: dict[str, Any]


class ComparisonEngine:
    """Computes deltas between a baseline run score and a candidate run score.

    The engine is initialized with the ScenarioPack so it can resolve
    scenario metadata (tags, families) for the per-family aggregation.

    Args:
        pack: The ScenarioPack containing the scenario definitions.
            Used to resolve scenario tags for per-family aggregation.
    """

    def __init__(self, pack: ScenarioPack) -> None:
        self._pack = pack
        self._scenario_map = {s.id: s for s in pack.scenarios}

    def compare(
        self,
        baseline_score: RunScore,
        candidate_score: RunScore,
        baseline: Baseline,
        candidate_artifacts: list[Any] | None = None,
        candidate_adapter_manifest: dict[str, Any] | None = None,
        allow_adapter_change: bool = False,
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
                cost delta computation and model/adapter detection).
            candidate_adapter_manifest: Optional adapter manifest dict from
                the candidate run. Compared against baseline.adapter_manifest
                to detect adapter changes.
            allow_adapter_change: When True, suppresses adapter change
                detection (useful for intentional adapter swaps).

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
            status_regressed = (
                base_ss is not None and cand_ss is not None
                and base_ss.status == "passed" and cand_ss.status != "passed"
            )
            status_improved = (
                base_ss is not None and cand_ss is not None
                and base_ss.status != "passed" and cand_ss.status == "passed"
            )
            score_regressed = delta is not None and delta < -SCORE_DELTA_THRESHOLD
            score_improved = delta is not None and delta > SCORE_DELTA_THRESHOLD
            failure_category = self._classify_outcome(cand_ss)
            scenario_deltas[sid] = {
                "baseline_score": base_score,
                "candidate_score": cand_score,
                "delta": delta,
                "baseline_status": base_ss.status if base_ss else None,
                "candidate_status": cand_ss.status if cand_ss else None,
                "regressed": status_regressed or score_regressed,
                "improved": status_improved or score_improved,
                "new_failure": (
                    base_ss is None and cand_ss is not None and cand_ss.status != "passed"
                ),
                "new_pass": base_ss is None and cand_ss is not None and cand_ss.status == "passed",
                "score_delta_regressed": score_regressed,
                "score_delta_improved": score_improved,
                "failure_category": failure_category,
                "safety_violations": cand_ss.safety_violations if cand_ss else [],
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

        # Adapter change detection: a divergent adapter manifest means the
        # observation path changed, which is distinct from an agent regression.
        adapter_changed = False
        if (
            not allow_adapter_change
            and baseline.adapter_manifest is not None
            and candidate_adapter_manifest is not None
        ):
            baseline_digest = baseline.adapter_manifest.get("digest", "")
            candidate_digest = candidate_adapter_manifest.get("digest", "")
            if baseline_digest and candidate_digest and baseline_digest != candidate_digest:
                adapter_changed = True

        # Model change detection: a different agent model is a distinct outcome
        # from "the agent got worse". Only flagged when the baseline records a
        # model and the candidate artifacts expose one.
        model_changed = False
        baseline_model = (baseline.agent or {}).get("model")
        if baseline_model:
            candidate_model = _candidate_model(candidate_artifacts)
            if candidate_model and candidate_model != baseline_model:
                model_changed = True

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
            "adapter_changed": adapter_changed,
            "model_changed": model_changed,
        }

        return ComparisonResult(
            scenario_deltas=scenario_deltas,
            family_deltas=family_deltas,
            aggregate=aggregate,
        )

    @staticmethod
    def _classify_outcome(cand_ss: ScenarioScore | None) -> str | None:
        """Classify into adapter_failed/agent_crashed/scenario_failed.

        Uses :class:`FailureTaxonomy` to classify the candidate scenario.
        Maps taxonomy categories to the three-way split:
        - ``adapter_failed``: infrastructure issues (schema errors, tool errors)
        - ``agent_crashed``: agent crashed or timed out
        - ``scenario_failed``: agent ran but produced wrong/incomplete output
        - ``None``: scenario passed

        Args:
            cand_ss: Candidate ScenarioScore object.

        Returns:
            A string label or None if the scenario passed.
        """
        if cand_ss is None or cand_ss.status == "passed":
            return None
        try:
            fc = FailureTaxonomy.classify(cand_ss)
            if fc is None:
                return None
            cat = fc.category.value if hasattr(fc.category, "value") else str(fc.category)
            if cat in ("timeout", "agent_crash"):
                return "agent_crashed"
            if cat in ("tool_error", "schema_error", "budget_exceeded"):
                return "adapter_failed"
            return "scenario_failed"
        except Exception:
            return "scenario_failed"

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

    Args:
        values: List of float values.

    Returns:
        The mean, or 0.0 if the list is empty.
    """
    return sum(values) / len(values) if values else 0.0


def _candidate_model(candidate_artifacts: list[Any] | None) -> str | None:
    """Extract the model name from the first candidate artifact that records one.

    Model info is read from each artifact's sanitized ``agent`` dict
    (``agent["model"]``). Returns the first non-empty value found, or None
    if the candidate exposes no model.

    Args:
        candidate_artifacts: The candidate's RunArtifacts.

    Returns:
        The model name string, or None if unknown.
    """
    for a in candidate_artifacts or []:
        agent = getattr(a, "agent", None)
        model = agent.get("model") if isinstance(agent, dict) else None
        if model:
            return model  # type: ignore[no-any-return]
    return None


def _sum_cost(artifacts: list[Any]) -> float:
    """Sum the cost_usd field across a list of artifacts.

    Safely handles artifacts that may not have a cost field (e.g., the
    item is a dict or lacks the attribute) by using getattr with defaults.

    Args:
        artifacts: List of artifacts (RunArtifact or dict-like) with
            optional ``cost.cost_usd`` attribute.

    Returns:
        The total cost in USD, rounded to 6 decimal places.
    """
    total = 0.0
    for a in artifacts:
        c = getattr(a, "cost", None)
        if c is not None:
            total += getattr(c, "cost_usd", 0.0) or 0.0
    return round(total, 6)
