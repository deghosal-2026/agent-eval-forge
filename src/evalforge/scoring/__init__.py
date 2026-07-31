"""Scoring engine — deterministic, judge, and hybrid scatter."""

# Force registration of all built-in scorers
from evalforge.scoring.base import Scorer
from evalforge.scoring.deterministic import (  # noqa: F401
    args,
    budget,
    gates,
    output,
    tools,
)
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge.scorers import *  # noqa: F403
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
