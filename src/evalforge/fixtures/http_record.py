"""HTTP request/response recording and replay (VCR-style cassettes).

Provides :class:`HTTPRecording` for recording HTTP interactions as cassettes
and replaying them during deterministic evaluation. Supports save/load
to/from JSON files for persistent fixture storage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HTTPExchange:
    """A single recorded HTTP request/response pair.

    Attributes:
        request: The request dict (typically with ``method``, ``uri``, ``headers``).
        response: The response dict (typically with ``status``, ``headers``, ``body``).
    """

    request: dict[str, Any]
    response: dict[str, Any]


class HTTPRecording:
    """VCR-style HTTP interaction recording and replay.

    Records HTTP exchanges into named cassettes (in-memory), persists them
    to JSON files via :meth:`save_cassette`, and replays from memory via
    :meth:`replay`. Supports loading pre-recorded cassettes from disk.
    """

    def __init__(self, cassette_dir: str) -> None:
        """Initialize the HTTP recording system.

        Args:
            cassette_dir: Directory for loading/saving cassette JSON files.
        """
        self._cassette_dir = Path(cassette_dir)
        self._cassettes: dict[str, list[HTTPExchange]] = {}

    def record(self, cassette_name: str, request: dict[str, Any], response: dict[str, Any]) -> None:
        """Record an HTTP exchange into a named cassette.

        Args:
            cassette_name: Name of the cassette to record into.
            request: The request details.
            response: The response details.
        """
        if cassette_name not in self._cassettes:
            self._cassettes[cassette_name] = []
        self._cassettes[cassette_name].append(
            HTTPExchange(request=request, response=response)
        )

    def replay(self, cassette_name: str, url: str, method: str) -> dict[str, Any]:
        """Replay a recorded response matching a URL and method.

        Args:
            cassette_name: Name of the cassette to replay from.
            url: The request URL to match.
            method: The HTTP method to match.

        Returns:
            The matching response dict.

        Raises:
            KeyError: If the cassette or matching interaction is not found.
        """
        if cassette_name not in self._cassettes:
            raise KeyError(f"No cassette named '{cassette_name}'")
        for exchange in self._cassettes[cassette_name]:
            req = exchange.request
            if req.get("uri") == url and req.get("method", "").upper() == method.upper():
                return exchange.response
        raise KeyError(
            f"No recorded interaction for {method.upper()} {url} in cassette '{cassette_name}'"
        )

    def save_cassette(self, cassette_name: str, path: str | None = None) -> None:
        """Persist a cassette to a JSON file.

        Args:
            cassette_name: Name of the cassette to save.
            path: Optional file path. Defaults to
                ``<cassette_dir>/<cassette_name>.json``.

        Raises:
            KeyError: If the cassette does not exist.
        """
        if cassette_name not in self._cassettes:
            raise KeyError(f"No cassette named '{cassette_name}'")
        target = Path(path) if path else self._cassette_dir / f"{cassette_name}.json"
        interactions = [
            {
                "request": ex.request,
                "response": ex.response,
            }
            for ex in self._cassettes[cassette_name]
        ]
        cassette = {"version": 1, "interactions": interactions}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(cassette, indent=2))

    def load_cassette(self, path: str) -> str:
        """Load a cassette from a JSON file into memory.

        Args:
            path: Path to the cassette JSON file.

        Returns:
            The cassette name (derived from the file stem).
        """
        cassette_path = Path(path)
        data = json.loads(cassette_path.read_text())
        cassette_name = cassette_path.stem
        self._cassettes[cassette_name] = []
        for interaction in data.get("interactions", []):
            self._cassettes[cassette_name].append(
                HTTPExchange(
                    request=interaction["request"],
                    response=interaction["response"],
                )
            )
        return cassette_name

    def interactions(self, cassette_name: str) -> list[HTTPExchange]:
        """Get all recorded interactions for a cassette.

        Args:
            cassette_name: Name of the cassette.

        Returns:
            A list of :class:`HTTPExchange` objects.

        Raises:
            KeyError: If the cassette does not exist.
        """
        if cassette_name not in self._cassettes:
            raise KeyError(f"No cassette named '{cassette_name}'")
        return list(self._cassettes[cassette_name])
