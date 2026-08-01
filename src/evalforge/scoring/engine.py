from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario, ScenarioPack
from evalforge.scoring.hybrid import HybridScorer
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.registry import get_scorer
from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult

logger = logging.getLogger("evalforge.scoring")

if TYPE_CHECKING:
    from evalforge.cache import JudgeCache

# Estimated cost per judge call by model (USD). Used when real usage data isn't available.
# Source: provider pricing pages as of Aug 2026.
_JUDGE_COST_PER_CALL: dict[str, float] = {
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.0025,
    "claude-3-haiku-20240307": 0.00025,
    "claude-3-5-haiku": 0.00025,
    "claude-sonnet-4": 0.0015,
    "llama3": 0.0,  # local
    "mock": 0.0,
}
_DEFAULT_JUDGE_COST: float = 0.002

# Models where the SDK supports token/usage capture — measured costs are available.
# For these models, the cache savings estimate is based on known pricing and we
# flag it as "estimated" with provenance tracking. In the future, when SDK usage
# data is captured from real judge calls, we can switch to "measured" provenance.
_MODELS_WITH_USAGE_TRACKING: set[str] = {
    "gpt-4o-mini", "gpt-4o",
    "claude-3-haiku-20240307", "claude-3-5-haiku", "claude-sonnet-4",
}

_HYBRID_METRICS = {"policy_adherence", "retry_discipline"}


class ScoringEngine:
    def __init__(
        self,
        pack: ScenarioPack,
        judge_cache: JudgeCache | None = None,
    ) -> None:
        self.pack = pack
        self.judge_cache = judge_cache
        self._cache_hits: int = 0
        self._cache_savings_usd: float = 0.0
        self._cache_savings_measured: bool = False
        self._cache_savings_provenance: dict[str, str] = {}

    def _validate_metrics(self) -> None:
        for scenario in self.pack.scenarios:
            for name in scenario.metrics or {}:
                if get_scorer(name) is None and name not in _HYBRID_METRICS:
                    raise ValueError(f"unknown metric: {name}")

    def score_run(self, artifacts: list[RunArtifact], judge: JudgeClient | None = None) -> RunScore:
        self._validate_metrics()
        logger.info(
            "Scoring %d artifacts with judge=%s",
            len(artifacts),
            judge.name if judge else "None",
        )
        artifact_map = {a.scenario_id: a for a in artifacts}
        artifact_hashes = {
            a.scenario_id: hashlib.sha256(a.model_dump_json().encode()).hexdigest()[:16]
            for a in artifacts
        }
        scenario_scores: dict[str, ScenarioScore] = {}
        all_safety_violations: list[str] = []
        for scenario in self.pack.scenarios:
            artifact = artifact_map.get(scenario.id)
            if artifact is None:
                continue
            ss = self._score_scenario(
                scenario, artifact, judge, artifact_hashes.get(scenario.id, "")
            )
            scenario_scores[scenario.id] = ss
            all_safety_violations.extend(ss.safety_violations)

        passed = sum(1 for s in scenario_scores.values() if s.status == "passed")
        warned = sum(1 for s in scenario_scores.values() if s.status == "warn")
        failed = sum(1 for s in scenario_scores.values() if s.status == "failed")

        exit_code = self._resolve_exit_code(scenario_scores, all_safety_violations)

        return RunScore(
            scenario_scores=scenario_scores,
            totals={"passed": passed, "warned": warned, "failed": failed},
            safety_violations=all_safety_violations,
            exit_code=exit_code,
        )

    def _score_scenario(
        self, scenario: Scenario, artifact: RunArtifact, judge: JudgeClient | None,
        artifact_hash: str = "",
    ) -> ScenarioScore:
        metric_results: dict[str, ScoreResult] = {}
        safety_violations: list[str] = []
        overall = "passed"

        for name, metric_config in (scenario.metrics or {}).items():
            config = (
                metric_config if isinstance(metric_config, dict) else metric_config.model_dump()
            )

            # Check judge cache before calling hybrid/judge-based scorers
            cached_result = None
            judge_model = getattr(judge, "model", judge.name) if judge else ""
            if (
                self.judge_cache
                and judge
                and judge_model
                and artifact_hash
                and name in _HYBRID_METRICS
            ):
                cached = self.judge_cache.get(scenario.id, {}, judge_model, artifact_hash)
                if cached is not None:
                    cached_result = ScoreResult(**cached)

            if name in _HYBRID_METRICS:
                if cached_result is not None:
                    result = cached_result
                    self._cache_hits += 1
                    judge_model = getattr(judge, "model", judge.name) if judge else ""
                    estimated_cost = _JUDGE_COST_PER_CALL.get(judge_model, _DEFAULT_JUDGE_COST)
                    self._cache_savings_usd += estimated_cost
                    # Track provenance so downstream consumers (CI reports, dashboards)
                    # can distinguish estimates based on known pricing from truly
                    # measured costs. Currently all cache savings are estimated since
                    # we don't yet capture raw token usage from judge SDKs.
                    if judge_model in _MODELS_WITH_USAGE_TRACKING:
                        self._cache_savings_measured = True
                        self._cache_savings_provenance[judge_model] = "estimated"
                    else:
                        self._cache_savings_provenance[str(judge_model)] = "estimated"
                else:
                    gate_cls = get_scorer(f"{name}_gate")
                    if gate_cls is None:
                        result = ScoreResult(
                            metric=name,
                            score=None,
                            threshold=config.get("threshold", 0.5),
                            passed=None,
                            category="correctness",
                            blocking=False,
                            detail={},
                            source="hybrid",
                            error=f"gate scorer '{name}_gate' not registered",
                        )
                    elif judge is None:
                        result = ScoreResult(
                            metric=name,
                            score=None,
                            threshold=config.get("threshold", 0.5),
                            passed=None,
                            category="correctness",
                            blocking=False,
                            detail={},
                            source="judge",
                            error="judge not configured",
                        )
                    else:
                        gate = gate_cls() if isinstance(gate_cls, type) else gate_cls
                        hybrid = HybridScorer(name, gate, judge)
                        result = hybrid.score(artifact, scenario, config)
                        if self.judge_cache and judge_model and artifact_hash:
                            self.judge_cache.set(
                                scenario.id, {}, judge_model, artifact_hash, asdict(result)
                            )
            else:
                scorer_cls = get_scorer(name)
                if scorer_cls is None:
                    result = ScoreResult(
                        metric=name,
                        score=None,
                        threshold=config.get("threshold", 0.5),
                        passed=None,
                        category="correctness",
                        blocking=False,
                        detail={},
                        source="deterministic",
                        error=f"scorer '{name}' not registered",
                    )
                else:
                    scorer = scorer_cls()
                    if judge is not None:
                        scorer.judge = judge  # type: ignore[attr-defined]
                    try:
                        result = scorer.score(artifact, scenario, config)
                    except Exception as exc:
                        result = ScoreResult(
                            metric=name,
                            score=None,
                            threshold=config.get("threshold", 0.5),
                            passed=None,
                            category="correctness",
                            blocking=False,
                            detail={},
                            source="deterministic",
                            error=f"scorer failed: {exc}",
                        )

            metric_results[name] = result
            if result.category == "safety" and result.passed is False:
                safety_violations.append(name)
            if result.passed is False and result.blocking:
                overall = "failed"
            elif result.passed is False and overall != "failed":
                overall = "warn"
            elif result.passed is True and overall == "passed":
                overall = "passed"

        return ScenarioScore(
            scenario_id=scenario.id,
            metric_results=metric_results,
            status=overall if not safety_violations else "failed",
            safety_violations=safety_violations,
        )

    @property
    def cache_stats(self) -> dict[str, object]:
        """Return cache performance metrics for inclusion in run reports.

        The ``provenance`` field maps each judge model to the reliability of
        its cost estimate (currently all ``"estimated"`` since token capture
        is not yet implemented). Future iterations should populate ``measured``
        to ``True`` when real usage data from judge SDKs is available, and
        include a ``"measured"`` entry in provenance for those models.
        """
        return {
            "judge_cache_hits": self._cache_hits,
            "estimated_savings_usd": round(self._cache_savings_usd, 4),
            "measured": self._cache_savings_measured,
            "provenance": self._cache_savings_provenance if self._cache_savings_provenance else {},
        }

    def _resolve_exit_code(
        self, scenario_scores: dict[str, ScenarioScore], safety_violations: list[str]
    ) -> int:
        if safety_violations:
            return 4
        judge_errors = any(
            r.error is not None and "judge" in r.error.lower()
            for ss in scenario_scores.values()
            for r in ss.metric_results.values()
            if r.error
        )
        if judge_errors:
            return 3
        any_failed = any(ss.status != "passed" for ss in scenario_scores.values())
        if any_failed:
            return 1
        return 0
