"""Seed manager — deterministic PRNG for reproducible evaluation runs.

Manages a top-level seed and derives per-scenario seeds via SHA-256 so that
every scenario gets a unique but deterministic random stream.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any


@dataclass
class DeterminismConfig:
    """Configuration for deterministic evaluation runs.

    Attributes:
        seed: Base seed for all random operations.
        freeze_time: Whether to freeze ``time.time`` during the run.
        freeze_random: Whether to seed the global ``random`` module.
        order_scenarios: Whether to sort scenarios for a fixed execution order.
        record_mode: Recording mode (``"none"``, ``"record"``, ``"replay"``).
    """
    seed: int = 42
    freeze_time: bool = True
    freeze_random: bool = True
    order_scenarios: bool = True
    record_mode: str = "none"


class SeedManager:
    """Deterministic seed management with per-scenario derived seeds.

    Maintains its own ``random.Random`` instance (independent of the global
    module) and provides deterministic per-scenario seeds.

    Args:
        seed: Base seed value. Defaults to 42.
    """

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._rng = random.Random(seed)  # noqa: S311
        self._initial_state = self._rng.getstate()

    def set_global_seed(self) -> None:
        """Seed the global ``random``, ``numpy.random``, and ``torch`` modules.

        This makes third-party code that uses these global PRNGs reproducible.
        """
        random.seed(self._seed)
        try:
            import numpy as np
            np.random.seed(self._seed)
        except ImportError:
            pass
        try:
            import torch  # type: ignore[import-not-found]
            torch.manual_seed(self._seed)
        except ImportError:
            pass

    def scenario_seed(self, scenario_id: str) -> int:
        """Derive a deterministic per-scenario seed from the base seed.

        Uses SHA-256 of ``"{base_seed}:{scenario_id}"`` and reduces to
        a 31-bit integer.

        Args:
            scenario_id: Scenario identifier.

        Returns:
            A deterministic integer in [0, 2**31).
        """
        digest = hashlib.sha256(
            f"{self._seed}:{scenario_id}".encode()
        ).digest()
        return int.from_bytes(digest[:8], "big") % (2**31)

    def reset(self) -> None:
        """Reset the internal PRNG to its initial state."""
        self._rng = random.Random(self._seed)  # noqa: S311
        self._rng.setstate(self._initial_state)

    @property
    def rng(self) -> random.Random:
        """Return the internal PRNG instance."""
        return self._rng

    @property
    def seed(self) -> int:
        """Return the base seed value."""
        return self._seed

    def getstate(self) -> Any:
        """Return the current internal PRNG state (for save/restore)."""
        return self._rng.getstate()

    def setstate(self, state: Any) -> None:
        """Restore the internal PRNG state from a previous ``getstate()`` call.

        Args:
            state: A state tuple as returned by ``getstate()``.
        """
        self._rng.setstate(state)
