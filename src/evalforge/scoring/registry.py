"""Scorer registry — decorator, lookup, aliases, entry-point discovery."""

from __future__ import annotations

from evalforge.models.errors import ConfigError
from evalforge.scoring.base import Scorer

SCORERS: dict[str, type[Scorer]] = {}

# Spec catalog name → launch-pack name. Aliases let get_scorer resolve
# catalog names (e.g. "schema_valid" → "schema_validity").
ALIASES: dict[str, str] = {
    "exact_match": "tool_correctness",
    "schema_valid": "schema_validity",
    "field_presence": "field_correctness",
    "tool_not_called": "zero_disallowed_actions",
    "tool_args_match": "argument_correctness",
    "step_count": "step_efficiency",
    "cost_budget": "cost_budget_adherence",
    "policy_adherence": "task_completion",
    "retry_discipline": "output_correctness",
}


def register_scorer(cls: type[Scorer]) -> type[Scorer]:
    if not cls.name:
        raise ConfigError(f"Scorer {cls.__name__} has empty name")
    if cls.name in SCORERS:
        raise ConfigError(f"Duplicate scorer registration: {cls.name}")
    SCORERS[cls.name] = cls
    return cls


def get_scorer(name: str) -> type[Scorer] | None:
    if name in SCORERS:
        return SCORERS[name]
    alias = ALIASES.get(name)
    if alias:
        return SCORERS.get(alias)
    return None


def discover_entry_points() -> None:
    """Discover externally registered scorers via entry points. No-op in M2."""
