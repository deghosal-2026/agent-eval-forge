"""Scoring engine — deterministic, judge, and hybrid scatter."""

from evalforge.scoring.base import Scorer
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.registry import (
    ALIASES,
    SCORERS,
    discover_entry_points,
    get_scorer,
    register_scorer,
)
from evalforge.scoring.result import JudgeVerdict, RunScore, ScenarioScore, ScoreResult

__all__ = [
    "ALIASES",
    "SCORERS",
    "JudgeVerdict",
    "RunScore",
    "ScenarioScore",
    "ScoreResult",
    "Scorer",
    "ScoringEngine",
    "discover_entry_points",
    "get_scorer",
    "register_scorer",
]