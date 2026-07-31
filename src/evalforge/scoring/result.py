"""Scoring result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreResult:
    metric: str
    score: float | None
    threshold: float | None
    passed: bool | None
    category: str  # "safety" | "correctness" | "efficiency"
    blocking: bool
    detail: dict[str, object]
    source: str  # "deterministic" | "judge"
    error: str | None


@dataclass
class ScenarioScore:
    scenario_id: str
    metric_results: dict[str, ScoreResult]
    status: str  # "passed" | "warn" | "failed"
    safety_violations: list[str]


@dataclass
class RunScore:
    scenario_scores: dict[str, ScenarioScore]
    totals: dict[str, int]  # {"passed": int, "warned": int, "failed": int}
    safety_violations: list[str]
    exit_code: int  # 0 | 1 | 2 | 3 | 4


@dataclass
class JudgeVerdict:
    score: float
    rationale: str
