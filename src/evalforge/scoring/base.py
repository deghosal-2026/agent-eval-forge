"""Scorer abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.result import ScoreResult


class Scorer(ABC):
    name: str = ""
    category: str = "correctness"

    @abstractmethod
    def score(
        self,
        artifact: RunArtifact,
        scenario: Scenario,
        metric_config: dict[str, Any],
    ) -> ScoreResult: ...
