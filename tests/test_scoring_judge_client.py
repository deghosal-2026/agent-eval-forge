import pytest

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.mock import MockJudge


def test_judge_client_abc() -> None:
    with pytest.raises(TypeError):
        type("Missing", (JudgeClient,), {})()


def test_mock_judge_returns_configured_verdict() -> None:
    judge = MockJudge(score=0.75, rationale="decent")
    verdict = judge.judge("some prompt")
    assert verdict.score == 0.75
    assert verdict.rationale == "decent"


def test_mock_judge_default_verdict() -> None:
    judge = MockJudge()
    verdict = judge.judge("any")
    assert verdict.score == 1.0
    assert "mock" in verdict.rationale.lower()


def test_openai_client_name() -> None:
    from evalforge.scoring.judge.openai import OpenAIClient

    client = OpenAIClient(api_key="test")
    assert client.name == "openai"
