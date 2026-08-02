"""Scorer registry — decorator, lookup, aliases, entry-point discovery.

Maintains a global registry of all known :class:`Scorer` classes. Scorers
register themselves via the :func:`register_scorer` decorator at import time.
The registry supports aliases so that spec catalog names (e.g. ``"exact_match"``)
can be resolved to launch-pack names (e.g. ``"tool_correctness"``).
"""

from __future__ import annotations

from evalforge.models.errors import ConfigError
from evalforge.scoring.base import Scorer

# Global registry mapping scorer name → Scorer subclass.
# Populated by @register_scorer decorators at import time.
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
    """Register a Scorer class in the global SCORERS registry.

    Used as a decorator on Scorer subclasses. The class must set ``name``
    to a non-empty string. Duplicate names raise ConfigError.

    Args:
        cls: A Scorer subclass to register.

    Returns:
        The same class, unmodified.

    Raises:
        ConfigError: If ``cls.name`` is empty or a scorer with that name
            is already registered.
    """
    if not cls.name:
        raise ConfigError(f"Scorer {cls.__name__} has empty name")
    if cls.name in SCORERS:
        raise ConfigError(f"Duplicate scorer registration: {cls.name}")
    SCORERS[cls.name] = cls
    return cls


def get_scorer(name: str) -> type[Scorer] | None:
    """Look up a Scorer class by name or alias.

    Checks the SCORERS registry first, then falls back to alias resolution
    via ALIASES.

    Args:
        name: The metric name (e.g. ``"tool_correctness"``) or catalog alias
            (e.g. ``"exact_match"``).

    Returns:
        The registered Scorer class, or None if not found.
    """
    if name in SCORERS:
        return SCORERS[name]
    alias = ALIASES.get(name)
    if alias:
        return SCORERS.get(alias)
    return None


def discover_entry_points() -> None:
    """Discover externally registered scorers via entry points. No-op in M2."""
