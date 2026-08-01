from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class FixtureNotFoundError(KeyError):
    """Raised when a fixture file is missing for a requested tool."""


class ToolStub:
    """Intercepts tool calls and returns deterministic fixture data.

    In ``--fixtures`` mode, every tool call an agent makes is intercepted and
    answered from a JSON fixture file rather than a live service. This makes
    runs fully deterministic and fast.
    """

    def __init__(self, fixtures_dir: str | Path = "scenarios/fixtures") -> None:
        self._fixtures_dir = Path(fixtures_dir)
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._delay_ms: int = 0

    def set_delay_ms(self, delay_ms: int) -> None:
        self._delay_ms = delay_ms

    def _load_fixtures(self, tool_name: str) -> list[dict[str, Any]]:
        if tool_name in self._cache:
            return self._cache[tool_name]
        fixture_path = self._fixtures_dir / f"{tool_name}.json"
        if not fixture_path.exists():
            raise FixtureNotFoundError(
                f"No fixture file for tool '{tool_name}': {fixture_path} not found"
            )
        data = json.loads(fixture_path.read_text())
        if not isinstance(data, list):
            data = [data]
        self._cache[tool_name] = data
        return data

    def intercept(self, tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a deterministic fixture response for the given tool call.

        If multiple fixture entries exist, cycles through them round-robin
        based on a hash of the payload for consistent replay.
        """
        if self._delay_ms:
            time.sleep(self._delay_ms / 1000.0)
        fixtures = self._load_fixtures(tool_name)
        if len(fixtures) == 1:
            return fixtures[0]
        idx = 0
        if payload:
            idx = hash(json.dumps(payload, sort_keys=True)) % len(fixtures)
        return fixtures[idx]

    def available_tools(self) -> set[str]:
        if not self._fixtures_dir.exists():
            return set()
        return {f.stem for f in self._fixtures_dir.glob("*.json")}