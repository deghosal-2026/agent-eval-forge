"""EnvironmentFreezer — freezes time, random state, and hash seeds for determinism.

Patches ``time.time``, ``datetime.datetime``, ``random`` state, and
``PYTHONHASHSEED`` so that evaluation runs are fully reproducible.
"""

from __future__ import annotations

import datetime
import os
import random
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


class _FrozenDatetime(datetime.datetime):
    """A datetime subclass that always returns a fixed timestamp (2024-01-01)."""

    @classmethod
    def now(cls, tz: datetime.tzinfo | None = None) -> _FrozenDatetime:
        return cls(2024, 1, 1, 0, 0, 0, tzinfo=tz or datetime.UTC)

    @classmethod
    def utcnow(cls) -> _FrozenDatetime:
        return cls(2024, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)


class EnvironmentFreezer:
    """Context manager that freezes environment sources of non-determinism.

    When entered, patches:

    - ``time.time`` to return a fixed timestamp
    - ``datetime.datetime`` to a frozen subclass
    - ``random`` state to a seeded state
    - ``PYTHONHASHSEED`` to ``"0"``
    - ``numpy.random`` to seed 42 (if numpy is available)

    On exit, all patches are reverted and the original random state is restored.
    """

    def __init__(
        self,
        frozen_time: float | None = None,
        frozen_datetime: datetime.datetime | None = None,
    ) -> None:
        """Initialise with optional custom freeze values.

        Args:
            frozen_time: Unix timestamp to freeze ``time.time`` to.
                Defaults to ``1704067200.0`` (2024-01-01T00:00:00Z).
            frozen_datetime: Datetime for frozen ``datetime.datetime``.
                Defaults to 2024-01-01 00:00:00 UTC.
        """
        self._frozen_time = frozen_time if frozen_time is not None else 1704067200.0
        self._frozen_dt = frozen_datetime or datetime.datetime(
            2024, 1, 1, 0, 0, 0, tzinfo=datetime.UTC,
        )
        self._original_time = time.time
        self._original_datetime_now = datetime.datetime.now
        self._original_datetime_class = datetime.datetime
        self._original_random_state: Any | None = None
        self._original_hashseed: str | None = None

    def __enter__(self) -> EnvironmentFreezer:
        """Apply all freezes and return self."""
        time.time = lambda: self._frozen_time
        datetime.datetime = _FrozenDatetime  # type: ignore[misc]

        self._original_random_state = random.getstate()
        random.seed(42)

        self._original_hashseed = os.environ.get("PYTHONHASHSEED")
        os.environ["PYTHONHASHSEED"] = "0"

        try:
            import numpy as np
            np.random.seed(42)
        except ImportError:
            pass

        return self

    def __exit__(self, *args: object) -> None:
        """Restore all original functions and state."""
        time.time = self._original_time
        datetime.datetime = self._original_datetime_class  # type: ignore[misc]

        if self._original_random_state is not None:
            random.setstate(self._original_random_state)

        if self._original_hashseed is not None:
            os.environ["PYTHONHASHSEED"] = self._original_hashseed
        elif "PYTHONHASHSEED" in os.environ:
            del os.environ["PYTHONHASHSEED"]

    @staticmethod
    @contextmanager
    def freeze_time(
        frozen_time: float | None = None,
    ) -> Generator[None, None, None]:
        """Context manager that only freezes time (not random or hash).

        Args:
            frozen_time: Unix timestamp to freeze to. Defaults to 1704067200.0.

        Yields:
            None
        """
        ft = frozen_time if frozen_time is not None else 1704067200.0
        original_time = time.time
        original_dt = datetime.datetime
        try:
            time.time = lambda: ft
            datetime.datetime = _FrozenDatetime  # type: ignore[misc]
            yield
        finally:
            time.time = original_time
            datetime.datetime = original_dt  # type: ignore[misc]

    @staticmethod
    @contextmanager
    def freeze_hash() -> Generator[None, None, None]:
        """Context manager that only freezes ``PYTHONHASHSEED`` to ``"0"``.

        Yields:
            None
        """
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ["PYTHONHASHSEED"] = "0"
            yield
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            elif "PYTHONHASHSEED" in os.environ:
                del os.environ["PYTHONHASHSEED"]
