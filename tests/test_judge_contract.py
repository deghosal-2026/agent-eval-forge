"""Contract tests for judge clients. Tests the control flow without real API keys."""

from __future__ import annotations

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.mock import MockJudge
from evalforge.scoring.judge.openai import OpenAIClient


class TestJudgeContract:
    """Verifies all judge clients follow the JudgeClient contract."""

    def test_mock_judge_is_client(self) -> None:
        j = MockJudge(score=1.0)
        assert isinstance(j, JudgeClient)
        result = j.judge("prompt")
        assert result.score == 1.0

    def test_mock_judge_score_range(self) -> None:
        for score in [0.0, 0.5, 1.0]:
            j = MockJudge(score=score)
            result = j.judge("prompt")
            assert 0.0 <= result.score <= 1.0

    def test_mock_judge_rationale(self) -> None:
        j = MockJudge(score=0.5)
        result = j.judge("test prompt")
        assert result.rationale

    def test_openai_client_requires_key(self) -> None:
        import os
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            # Without key, instantiation succeeds but calls fail
            client = OpenAIClient(api_key="", model="gpt-4o-mini")
            assert isinstance(client, JudgeClient)