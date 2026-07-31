"""Mock judge for testing."""

from __future__ import annotations

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.result import JudgeVerdict


class MockJudge(JudgeClient):
    name = "mock"

    def __init__(self, score: float = 1.0, rationale: str | None = None) -> None:
        self._score = score
        self._rationale = rationale

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        return JudgeVerdict(
            score=self._score,
            rationale=self._rationale or f"mock verdict for {len(prompt)} chars",
        )
