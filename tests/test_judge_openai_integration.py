"""Integration tests for OpenAI judge client (requires OPENAI_API_KEY).

Skipped by default unless OPENAI_API_KEY is set.
"""

from __future__ import annotations

import os

import pytest

from evalforge.models.artifact import RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import Metric, PackMetadata, Scenario, ScenarioPack
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge.openai import OpenAIClient
from evalforge.scoring.result import JudgeVerdict

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


@pytest.fixture
def client() -> OpenAIClient:
    return OpenAIClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model="gpt-4o-mini",
    )


class TestHappyPath:
    """Basic judge call returns a valid verdict."""

    def test_happy_path_verdict(self, client: OpenAIClient) -> None:
        prompt = (
            'Evaluate this response. Respond with JSON: {"score": 0.9, "rationale": "good"}'
        )
        verdict = client.judge(prompt)
        assert isinstance(verdict, JudgeVerdict)
        assert 0.0 <= verdict.score <= 1.0
        assert isinstance(verdict.rationale, str)

    def test_score_maps_to_range(self, client: OpenAIClient) -> None:
        prompt = 'Rate this as perfect. Respond with {"score": 1.0, "rationale": "perfect"}'
        verdict = client.judge(prompt)
        assert verdict.score == 1.0


class TestDiscrimination:
    """The judge should assign higher scores to correct answers."""

    def test_correct_scores_above_incorrect(self, client: OpenAIClient) -> None:
        correct_prompt = (
            'Judge this answer.\n\n'
            'Question: What is 2+2?\nAnswer: 4\n\n'
            'Respond with JSON: {"score": <0.0-1.0>, "rationale": "<reason>"}'
        )
        incorrect_prompt = (
            'Judge this answer.\n\n'
            'Question: What is 2+2?\nAnswer: 5\n\n'
            'Respond with JSON: {"score": <0.0-1.0>, "rationale": "<reason>"}'
        )
        correct = client.judge(correct_prompt)
        incorrect = client.judge(incorrect_prompt)
        assert correct.score > incorrect.score


class TestParseRobustness:
    """Edge-case inputs should not crash the client."""

    def test_special_characters_in_prompt(self, client: OpenAIClient) -> None:
        prompt = (
            'Rate: {"nested": "quotes", "escape": "\\\"}'
            '\n\nRespond with JSON: {"score": 0.5, "rationale": "ok"}'
        )
        verdict = client.judge(prompt)
        assert isinstance(verdict, JudgeVerdict)
        assert 0.0 <= verdict.score <= 1.0

    def test_long_prompt(self, client: OpenAIClient) -> None:
        long_text = "word " * 500
        prompt = (
            f'Rate this text: {long_text}\n\n'
            'Respond with JSON: {"score": 0.5, "rationale": "long text handled"}'
        )
        verdict = client.judge(prompt, max_tokens=1024)
        assert isinstance(verdict, JudgeVerdict)
        assert 0.0 <= verdict.score <= 1.0

    def test_empty_rationale_allowed(self, client: OpenAIClient) -> None:
        prompt = 'Respond with JSON: {"score": 0.0, "rationale": ""}'
        verdict = client.judge(prompt)
        assert verdict.score == 0.0
        assert verdict.rationale == ""


class TestFullPipeline:
    """Run ScoringEngine with a real OpenAI judge."""

    def test_full_pipeline(self, client: OpenAIClient) -> None:
        pack = ScenarioPack(
            pack=PackMetadata(name="test-pack", version="1.0"),
            scenarios=[
                Scenario(
                    id="test-scenario-1",
                    title="Test Scenario",
                    input="What is 2+2?",
                    metrics={"schema_validity": Metric(threshold=0.5)},
                ),
            ],
        )
        artifact = RunArtifact(
            id="artifact-1",
            scenario_id="test-scenario-1",
            timestamp=RunTimestamps(
                start="2026-01-01T00:00:00Z",
                end="2026-01-01T00:00:01Z",
                duration_ms=1000,
            ),
            output=RunOutput(final='{"answer": 4}'),
        )
        engine = ScoringEngine(pack)
        result = engine.score_run([artifact], judge=client)
        assert result.exit_code in (0, 1)
        assert "test-scenario-1" in result.scenario_scores
        ss = result.scenario_scores["test-scenario-1"]
        assert ss.metric_results["schema_validity"].passed is not None
