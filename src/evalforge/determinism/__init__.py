"""Determinism module — tools for reproducible evaluation runs.

Provides :class:`EnvironmentFreezer` to freeze time, random state, and hash
seeds, :class:`SeedManager` for deterministic PRNG, and
:class:`ReproducibilityChecker` to measure score/trajectory variance across runs.
"""

from evalforge.determinism.freeze import EnvironmentFreezer
from evalforge.determinism.reproducibility import ReproducibilityChecker, ReproducibilityReport
from evalforge.determinism.seed import DeterminismConfig, SeedManager

__all__ = [
    "DeterminismConfig",
    "EnvironmentFreezer",
    "ReproducibilityChecker",
    "ReproducibilityReport",
    "SeedManager",
]
