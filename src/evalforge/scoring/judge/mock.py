"""Mock judge for testing.

Returns a fixed score and rationale without making any API calls. Useful for
unit tests, integration tests, and CI scenarios where a real LLM judge is
unavailable or undesirable.
"""

from __future__ import annotations

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.result import JudgeVerdict


class MockJudge(JudgeClient):
    """Mock judge that returns a configured score for every prompt.

    Args:
        score: The fixed score to return (default 1.0).
        rationale: Optional rationale text. If None, generates a default
            message including the prompt length.
    """
    name = "mock"

    def __init__(self, score: float = 1.0, rationale: str | None = None) -> None:
        self._score = score
        self._rationale = rationale

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        """Return a fixed verdict regardless of the prompt.

        Args:
            prompt: The evaluation prompt (ignored except for generating
                a default rationale).
            max_tokens: Ignored by mock.
            temperature: Ignored by mock.

        Returns:
            A JudgeVerdict with the configured score and rationale.
        """
        return JudgeVerdict(
            score=self._score,
            rationale=self._rationale or f"mock verdict for {len(prompt)} chars",
        )
