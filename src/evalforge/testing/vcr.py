"""VCR-style record-and-replay for LangGraph agent LLM calls.

Layer 3: Deterministic replay using the existing HTTP recording infrastructure
(``http_record.py``) to capture LLM API calls and replay them with trajectory
verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evalforge.fixtures.http_record import HTTPRecording


@dataclass
class LLMCassette:
    """A recorded cassette of LLM API interactions.

    Attributes:
        name: Cassette identifier (used for file naming).
        interactions: List of dicts with keys ``request`` and ``response``
            representing each recorded API exchange.
    """
    name: str
    interactions: list[dict[str, Any]] = field(default_factory=list)


class LLMVCR:
    """VCR-style recorder/replayer for LLM API calls.

    Wraps :class:`HTTPRecording` to provide higher-level cassette management
    tailored for LLM interactions, including trajectory verification against
    recorded cassettes.

    Args:
        cassette_dir: Directory where cassette JSON files are stored.
            Defaults to ``tests/integration/cassettes``.
    """

    def __init__(self, cassette_dir: str = "tests/integration/cassettes") -> None:
        self._cassette_dir = Path(cassette_dir)
        self._recording = HTTPRecording(str(cassette_dir))
        self._current_cassette: str | None = None
        self._loaded_cassettes: dict[str, LLMCassette] = {}

    def start_recording(self, cassette_name: str) -> None:
        """Begin recording LLM interactions to *cassette_name*.

        Args:
            cassette_name: Identifier for the new cassette (used as file name stem).
        """
        self._current_cassette = cassette_name

    def stop_recording(self) -> None:
        """Stop recording and persist the current cassette to disk."""
        if self._current_cassette is None:
            return
        self._recording.save_cassette(self._current_cassette)
        self._current_cassette = None

    def replay(self, cassette_name: str) -> LLMCassette:
        """Load a cassette from disk and return its interactions.

        Args:
            cassette_name: Stem of the cassette file (without ``.json``).

        Returns:
            An :class:`LLMCassette` with the stored interactions.

        Raises:
            FileNotFoundError: If the cassette file does not exist.
        """
        cassette_path = self._cassette_dir / f"{cassette_name}.json"
        if not cassette_path.exists():
            raise FileNotFoundError(f"Cassette not found: {cassette_path}")
        self._recording.load_cassette(str(cassette_path))
        interactions = self._recording.interactions(cassette_name)
        cassette = LLMCassette(
            name=cassette_name,
            interactions=[
                {
                    "request": ex.request,
                    "response": ex.response,
                }
                for ex in interactions
            ],
        )
        self._loaded_cassettes[cassette_name] = cassette
        return cassette

    def get_llm_response(self, messages: list[dict[str, Any]], model: str) -> dict[str, Any]:
        """Fetch a replayed LLM response for the given messages from the current cassette.

        Args:
            messages: The prompt messages sent to the LLM.
            model: Model identifier (e.g. ``gpt-4o``).

        Returns:
            The replayed response dict.

        Raises:
            RuntimeError: If not currently recording.
        """
        if self._current_cassette is None:
            raise RuntimeError("Not currently recording. Call start_recording() first.")
        uri: str = f"llm://{model}/chat"
        method: str = "POST"
        response = self._recording.replay(
            self._current_cassette,
            uri,
            method,
        )
        return response

    def list_cassettes(self) -> list[str]:
        """List all cassette file stems in the cassette directory.

        Returns:
            Sorted list of cassette names (without ``.json`` extension).
        """
        if not self._cassette_dir.exists():
            return []
        return sorted(
            p.stem for p in self._cassette_dir.glob("*.json") if p.is_file()
        )

    def verify_trajectory(
        self, cassette: LLMCassette, actual_trajectory: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Compare an actual execution trajectory against a recorded cassette.

        Matches step-by-step on the ``messages`` field of each interaction.
        Any mismatch or difference in length is reported.

        Args:
            cassette: The :class:`LLMCassette` to compare against.
            actual_trajectory: List of step dicts from an actual run; each
                should contain a ``messages`` key.

        Returns:
            Dict with keys ``passed``, ``total_expected``, ``total_actual``,
            ``matched``, and ``mismatches``.
        """
        recorded = cassette.interactions
        mismatches: list[dict[str, Any]] = []
        match_count = 0
        for i, actual in enumerate(actual_trajectory):
            if i < len(recorded):
                rec = recorded[i]
                rec_body = rec.get("request", {}).get("body", {})
                rec_messages = rec_body.get("messages", [])
                actual_messages = actual.get("messages", [])
                if rec_messages == actual_messages:
                    match_count += 1
                else:
                    mismatches.append(
                        {
                            "index": i,
                            "expected": rec_messages,
                            "actual": actual_messages,
                        }
                    )
            else:
                mismatches.append(
                    {
                        "index": i,
                        "expected": None,
                        "actual": actual.get("messages", []),
                    }
                )
        # Report any recorded steps that were not executed
        for i in range(len(actual_trajectory), len(recorded)):
            rec = recorded[i]
            mismatches.append(
                {
                    "index": i,
                    "expected": rec.get("request", {}).get("body", {}).get("messages", []),
                    "actual": None,
                }
            )
        passed = len(mismatches) == 0 and len(actual_trajectory) == len(recorded)
        return {
            "passed": passed,
            "total_expected": len(recorded),
            "total_actual": len(actual_trajectory),
            "matched": match_count,
            "mismatches": mismatches,
        }
