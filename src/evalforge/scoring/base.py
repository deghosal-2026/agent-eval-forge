"""Scorer abstract base class.

Defines the :class:`Scorer` interface that all deterministic and judge-based
scorers must implement. Every scorer in the registry subclasses this ABC and
provides a ``score()`` method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.result import ScoreResult


class Scorer(ABC):
    """Abstract base class for all scorers in the scoring pipeline.

    Subclasses must set ``name`` and ``category`` as class-level attributes
    and implement :meth:`score`.

    Attributes:
        name: Unique identifier used in the SCORERS registry and in scenario
            metric definitions (e.g. ``"tool_correctness"``).
        category: One of ``"safety"``, ``"correctness"``, or ``"efficiency"``.
            Used for grouping and determining whether a failure is blocking.
    """
    name: str = ""
    category: str = "correctness"

    @abstractmethod
    def score(
        self,
        artifact: RunArtifact,
        scenario: Scenario,
        metric_config: dict[str, Any],
    ) -> ScoreResult:
        """Evaluate a single run artifact against a scenario.

        Args:
            artifact: The agent's run output (trajectory, final output, cost).
            scenario: The scenario definition containing expectations, budgets,
                allowed/disallowed tools, and metric configuration.
            metric_config: Per-metric configuration dict from the scenario
                definition (typically includes ``"threshold"``).

        Returns:
            A ScoreResult with score, pass/fail status, and detail metadata.
        """
        ...
