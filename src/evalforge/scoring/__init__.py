"""Scoring engine — deterministic, judge, and hybrid scatter.

This package provides the scoring subsystem for agent-eval-forge. It
defines the abstract Scorer interface, a registry of built-in scorers
(deterministic and LLM-as-judge), a hybrid scorer that gates judge calls
behind a deterministic fast path, and a ScoringEngine that orchestrates
evaluation across an entire scenario pack.

Sub-packages:
    deterministic/ — Rule-based scorers (tool usage, args, budget, gates, grounding, output).
    judge/         — LLM-as-judge scorers and provider-specific clients (OpenAI, Anthropic, MLX, Ollama).
"""

# Force registration of all built-in scorers by importing their modules.
# Each scorer file uses @register_scorer to populate the global SCORERS dict.
from evalforge.scoring.base import Scorer
from evalforge.scoring.deterministic import (  # noqa: F401
    args,
    budget,
    gates,
    grounding,
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

# Force registration of security evaluation scorers from the security sub-package.
from evalforge.security.evals import (
    DataExfiltrationPreventionScorer,
    PromptInjectionResistanceScorer,
    SandboxEscapeResistanceScorer,
    SecurityScenarioGenerator,
    SSRFPreventionScorer,
)

__all__ = [
    "ALIASES",
    "SCORERS",
    "DataExfiltrationPreventionScorer",
    "JudgeVerdict",
    "PromptInjectionResistanceScorer",
    "RunScore",
    "SSRFPreventionScorer",
    "SandboxEscapeResistanceScorer",
    "ScenarioScore",
    "ScoreResult",
    "Scorer",
    "ScoringEngine",
    "SecurityScenarioGenerator",
    "discover_entry_points",
    "get_scorer",
    "register_scorer",
]
