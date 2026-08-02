"""Repro minimizer — shrinks failing scenarios to minimal reproductions (X3).

Given a failing scenario and its artifact, repeatedly simplifies the input,
tool set, and expected values while preserving the failure signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MinimizeResult:
    """Result of a minimisation run.

    Attributes:
        original_input: The input string before minimisation.
        minimized_input: The shortest input that still triggers the failure.
        original_tool_count: Number of tools before minimisation.
        minimized_tool_count: Number of tools after minimisation.
        iterations: Number of minimisation iterations performed.
        reduction_pct: Percentage reduction in input length.
        still_fails: Whether the minimized input still produces the failure.
        failure_signature: Identifier of the original scenario (used as
            a proxy for the failure signature).
    """
    original_input: str
    minimized_input: str
    original_tool_count: int
    minimized_tool_count: int
    iterations: int
    reduction_pct: float
    still_fails: bool
    failure_signature: str


class ReproMinimizer:
    """Delta-debugging style minimizer for failing scenarios."""

    MAX_ITERATIONS = 50
    MIN_INPUT_LENGTH = 3

    def __init__(self) -> None:
        self._result: MinimizeResult | None = None

    def minimize(
        self,
        scenario_data: dict[str, Any],
        checker: Any,  # callable that returns True if scenario still fails
    ) -> MinimizeResult:
        """Run the minimisation loop.

        Alternates between reducing the input text and removing tools
        while checking that the failure persists.

        Args:
            scenario_data: Dict with keys ``input``, ``allowed_tools``, and
                optionally ``id``.
            checker: A callable that accepts a scenario dict and returns
                ``True`` if the failure is still present.

        Returns:
            A :class:`MinimizeResult` describing the best minimisation found.
        """
        original_input = scenario_data.get("input", "")
        original_tools = scenario_data.get("allowed_tools", [])

        current_input = original_input
        current_tools = list(original_tools)
        iterations = 0

        for _ in range(self.MAX_ITERATIONS):
            # Try halving the input; if that fails, try sentence-level shrink
            reduced = self._halve_input(current_input)
            if reduced == current_input:
                reduced = self._shrink_sentence(current_input)
            if reduced != current_input and len(reduced) >= self.MIN_INPUT_LENGTH:
                test_data = dict(scenario_data)
                test_data["input"] = reduced
                test_data["allowed_tools"] = current_tools
                iterations += 1
                try:
                    if checker(test_data):
                        current_input = reduced
                        continue
                except Exception:  # noqa: S110
                    pass

            # Try removing one tool at a time
            if len(current_tools) > 1:
                for i in range(len(current_tools)):
                    test_tools = current_tools[:i] + current_tools[i + 1:]
                    test_data = dict(scenario_data)
                    test_data["input"] = current_input
                    test_data["allowed_tools"] = test_tools
                    iterations += 1
                    try:
                        if checker(test_data):
                            current_tools = test_tools
                            break
                    except Exception:  # noqa: S110
                        pass

            break

        reduction_pct = (
            (1.0 - len(current_input) / max(len(original_input), 1)) * 100
            if original_input
            else 0.0
        )
        test_data = dict(scenario_data)
        test_data["input"] = current_input
        test_data["allowed_tools"] = current_tools
        try:
            still_fails = checker(test_data)
        except Exception:
            still_fails = False

        return MinimizeResult(
            original_input=original_input,
            minimized_input=current_input,
            original_tool_count=len(original_tools),
            minimized_tool_count=len(current_tools),
            iterations=iterations,
            reduction_pct=round(reduction_pct, 1),
            still_fails=still_fails,
            failure_signature=scenario_data.get("id", ""),
        )

    @staticmethod
    def _halve_input(text: str) -> str:
        """Return the first half of the input text.

        Args:
            text: The input string.

        Returns:
            First half (first ``len // 2`` characters), or the original
            string if it is at or below ``MIN_INPUT_LENGTH``.
        """
        if len(text) <= ReproMinimizer.MIN_INPUT_LENGTH:
            return text
        mid = len(text) // 2
        return text[:mid]

    @staticmethod
    def _shrink_sentence(text: str) -> str:
        """Return a reduced version by dropping lines or words.

        Prefers line-level reduction; if there is only one line, halves
        the word count.

        Args:
            text: The input string.

        Returns:
            A shorter string.
        """
        lines = text.split("\n")
        if len(lines) > 1:
            return lines[0]
        words = text.split()
        if len(words) > 1:
            return " ".join(words[: len(words) // 2])
        return text
