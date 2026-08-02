from __future__ import annotations

import datetime
import json
import os
import random
import time

from evalforge.determinism import (
    DeterminismConfig,
    EnvironmentFreezer,
    ReproducibilityChecker,
    SeedManager,
)
from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult


def _make_run_score(passed: int = 3, status: str = "passed") -> RunScore:
    scenario_scores: dict[str, ScenarioScore] = {}
    for i in range(3):
        sid = f"scenario_{i}"
        scenario_scores[sid] = ScenarioScore(
            scenario_id=sid,
            metric_results={
                "exact_match": ScoreResult(
                    metric="exact_match",
                    score=float(passed + i) / 4.0,
                    threshold=0.5,
                    passed=True,
                    category="correctness",
                    blocking=False,
                    detail={},
                    source="deterministic",
                    error=None,
                ),
            },
            status=status,
            safety_violations=[],
        )
    return RunScore(
        scenario_scores=scenario_scores,
        totals={"passed": 3, "warned": 0, "failed": 0},
        safety_violations=[],
        exit_code=0,
    )


class TestSeedManager:
    def test_consistent_seeds_per_scenario(self) -> None:
        sm = SeedManager(seed=42)
        s1 = sm.scenario_seed("scenario_a")
        s2 = sm.scenario_seed("scenario_a")
        assert s1 == s2

    def test_different_scenarios_different_seeds(self) -> None:
        sm = SeedManager(seed=42)
        s1 = sm.scenario_seed("scenario_a")
        s2 = sm.scenario_seed("scenario_b")
        assert s1 != s2

    def test_different_seeds_different_scenario_seeds(self) -> None:
        sm1 = SeedManager(seed=42)
        sm2 = SeedManager(seed=99)
        a1 = sm1.scenario_seed("scenario_a")
        a2 = sm2.scenario_seed("scenario_a")
        assert a1 != a2

    def test_reset_restores_rng(self) -> None:
        sm = SeedManager(seed=42)
        first = sm.rng.random()
        _ = sm.rng.random()
        _ = sm.rng.random()
        sm.reset()
        restored = sm.rng.random()
        assert first == restored

    def test_getstate_setstate_roundtrip(self) -> None:
        sm = SeedManager(seed=42)
        _ = sm.rng.random()
        _ = sm.rng.random()
        state = sm.getstate()
        val_before = sm.rng.random()
        sm.reset()
        sm.setstate(state)
        val_after = sm.rng.random()
        assert val_before == val_after

    def test_set_global_seed(self) -> None:
        sm = SeedManager(seed=12345)
        sm.set_global_seed()
        seq1 = [random.random() for _ in range(5)]
        random.seed(12345)
        seq2 = [random.random() for _ in range(5)]
        assert seq1 == seq2

    def test_scenario_seed_is_stable(self) -> None:
        sm = SeedManager(seed=42)
        expected = sm.scenario_seed("test_stable")
        for _ in range(10):
            assert sm.scenario_seed("test_stable") == expected

    def test_scenario_seed_range(self) -> None:
        sm = SeedManager(seed=42)
        for sid in [f"s{i}" for i in range(100)]:
            s = sm.scenario_seed(sid)
            assert 0 <= s < 2**31

    def test_seed_derivation_stable_across_instances(self) -> None:
        a = SeedManager(seed=42).scenario_seed("stable_test")
        b = SeedManager(seed=42).scenario_seed("stable_test")
        assert a == b

    def test_rng_is_independent(self) -> None:
        sm1 = SeedManager(seed=1)
        sm2 = SeedManager(seed=1)
        seq1 = [sm1.rng.random() for _ in range(5)]
        seq2 = [sm2.rng.random() for _ in range(5)]
        assert seq1 == seq2

    def test_seed_property(self) -> None:
        sm = SeedManager(42)
        assert sm.seed == 42


class TestReproducibilityChecker:
    def test_detects_consistent_runs(self) -> None:
        checker = ReproducibilityChecker()
        run1 = _make_run_score()
        run2 = _make_run_score()
        report = checker.check([run1, run2])
        assert report.consistent_scores
        assert report.runs == 2

    def test_detects_variance(self) -> None:
        checker = ReproducibilityChecker()
        run1 = _make_run_score(passed=3)
        run2 = _make_run_score(passed=2)
        report = checker.check([run1, run2])
        assert not report.consistent_scores

    def test_single_run_consistent(self) -> None:
        checker = ReproducibilityChecker()
        run1 = _make_run_score()
        report = checker.check([run1])
        assert report.consistent_scores
        assert "need at least 2 runs" in report.recommendations[0]

    def test_empty_runs(self) -> None:
        checker = ReproducibilityChecker()
        report = checker.check([])
        assert report.consistent_scores
        assert report.runs == 0

    def test_recommendations_on_variance(self) -> None:
        checker = ReproducibilityChecker()
        run1 = _make_run_score(passed=3)
        run2 = _make_run_score(passed=1)
        report = checker.check([run1, run2])
        assert not report.consistent_scores
        assert len(report.recommendations) > 0

    def test_report_has_seed_field(self) -> None:
        checker = ReproducibilityChecker()
        report = checker.check([_make_run_score(), _make_run_score()])
        assert report.seed == 0

    def test_score_variance_per_scenario(self) -> None:
        checker = ReproducibilityChecker()
        run1 = _make_run_score(passed=3)
        run2 = _make_run_score(passed=1)
        report = checker.check([run1, run2])
        assert "scenario_0" in report.score_variance
        assert report.score_variance["scenario_0"] > 0.0

    def test_three_run_check(self) -> None:
        checker = ReproducibilityChecker()
        runs = [_make_run_score(passed=3) for _ in range(3)]
        report = checker.check(runs)
        assert report.consistent_scores
        assert report.runs == 3


class TestEnvironmentFreezer:
    def test_freezes_time(self) -> None:
        with EnvironmentFreezer.freeze_time():
            t1 = time.time()
            t2 = time.time()
            assert t1 == t2
            assert t1 == 1704067200.0

    def test_freeze_time_custom_value(self) -> None:
        with EnvironmentFreezer.freeze_time(frozen_time=9999999.0):
            assert time.time() == 9999999.0

    def test_restores_time_after_context(self) -> None:
        before = time.time()
        with EnvironmentFreezer.freeze_time():
            pass
        after = time.time()
        assert after >= before

    def test_freezes_datetime(self) -> None:
        with EnvironmentFreezer.freeze_time():
            dt1 = datetime.datetime.now(datetime.UTC)
            dt2 = datetime.datetime.now(datetime.UTC)
            assert dt1 == dt2

    def test_restores_datetime_after_context(self) -> None:
        before = datetime.datetime.now(datetime.UTC)
        with EnvironmentFreezer.freeze_time():
            pass
        after = datetime.datetime.now(datetime.UTC)
        assert after >= before

    def test_freezer_context_manager(self) -> None:
        freezer = EnvironmentFreezer(frozen_time=12345.0)
        with freezer:
            assert time.time() == 12345.0
        assert time.time() > 12345.0

    def test_freezer_exit_restores(self) -> None:
        before = time.time()
        freezer = EnvironmentFreezer()
        with freezer:
            pass
        after = time.time()
        assert after >= before

    def test_freeze_hash_sets_env(self) -> None:
        original = os.environ.get("PYTHONHASHSEED")
        with EnvironmentFreezer.freeze_hash():
            assert os.environ["PYTHONHASHSEED"] == "0"
        assert os.environ.get("PYTHONHASHSEED") == original

    def test_freeze_hash_restores_original(self) -> None:
        original = os.environ.get("PYTHONHASHSEED")
        if original is not None:
            del os.environ["PYTHONHASHSEED"]
        try:
            with EnvironmentFreezer.freeze_hash():
                assert os.environ["PYTHONHASHSEED"] == "0"
            assert "PYTHONHASHSEED" not in os.environ
        finally:
            if original is not None:
                os.environ["PYTHONHASHSEED"] = original

    def test_freeze_hash_preserves_original_value(self) -> None:
        original = os.environ.get("PYTHONHASHSEED")
        os.environ["PYTHONHASHSEED"] = "123"
        try:
            with EnvironmentFreezer.freeze_hash():
                assert os.environ["PYTHONHASHSEED"] == "0"
            assert os.environ["PYTHONHASHSEED"] == "123"
        finally:
            if original is not None:
                os.environ["PYTHONHASHSEED"] = original
            elif "PYTHONHASHSEED" in os.environ:
                del os.environ["PYTHONHASHSEED"]


class TestDeterminismConfig:
    def test_defaults(self) -> None:
        cfg = DeterminismConfig()
        assert cfg.seed == 42
        assert cfg.freeze_time
        assert cfg.freeze_random
        assert cfg.order_scenarios
        assert cfg.record_mode == "none"

    def test_serialization_roundtrip(self) -> None:
        cfg = DeterminismConfig(seed=99, freeze_time=False)
        data = {"seed": cfg.seed, "freeze_time": cfg.freeze_time}
        json_str = json.dumps(data)
        loaded = json.loads(json_str)
        restored = DeterminismConfig(**loaded)  # type: ignore[arg-type]
        assert restored.seed == 99
        assert not restored.freeze_time

    def test_custom_config(self) -> None:
        cfg = DeterminismConfig(
            seed=123,
            freeze_time=False,
            freeze_random=False,
            order_scenarios=False,
            record_mode="record",
        )
        assert cfg.seed == 123
        assert not cfg.freeze_time


class TestScenarioOrdering:
    def test_deterministic_scenario_ordering(self) -> None:
        scenarios = ["zebra", "apple", "gamma", "beta"]
        sorted_a = sorted(scenarios)
        sorted_b = sorted(scenarios)
        assert sorted_a == sorted_b
        assert sorted_a == ["apple", "beta", "gamma", "zebra"]

    def test_consistent_order_across_calls(self) -> None:
        DeterminismConfig(order_scenarios=True)
        ids = [f"scenario_{i}" for i in range(20, 0, -1)]
        assert sorted(ids) == sorted(ids)

    def test_order_independent_of_insertion(self) -> None:
        ids1 = ["c", "b", "a"]
        ids2 = ["b", "a", "c"]
        assert sorted(ids1) == sorted(ids2)
