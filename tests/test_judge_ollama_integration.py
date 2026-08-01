"""Integration tests for local omlx judge (OpenAI-compatible endpoint).

Uses ``OpenAIClient`` pointed at a local omlx server running at
http://127.0.0.1:8000/v1 with model Qwen3.5-9B-MLX-4bit. The test probes
the endpoint before running and skips if the server is not reachable.
"""

from __future__ import annotations

import socket
from typing import Any

import httpx
import pytest

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.openai import OpenAIClient
from evalforge.scoring.result import JudgeVerdict

OMLX_BASE_URL = "http://127.0.0.1:8000/v1"
OMLX_MODEL = "Qwen3.5-9B-MLX-4bit"
OMLX_API_KEY = "omlx-test"


def _omlx_available() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        sock.connect(("127.0.0.1", 8000))
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _make_client(model: str = OMLX_MODEL) -> OpenAIClient:
    return OpenAIClient(
        api_key=OMLX_API_KEY,
        model=model,
        base_url=OMLX_BASE_URL,
        timeout=30.0,
    )


pytestmark = pytest.mark.omlx


@pytest.fixture(scope="module")
def omlx_client() -> OpenAIClient:
    if not _omlx_available():
        pytest.skip(f"omlx server not reachable at {OMLX_BASE_URL}")
    return _make_client()


class TestOmlxJudgeVerdicts:
    """Verify the omlx judge returns valid JudgeVerdict responses."""

    def test_happy_path(self, omlx_client: OpenAIClient) -> None:
        """Call judge with a valid prompt and get a properly structured verdict."""
        verdict = omlx_client.judge(
            "You are an evaluator.\n\n"
            "Question: What is the capital of France?\n"
            "Answer: Paris\n"
            "Expected Answer: Paris\n"
            "Criterion: Is the answer factually correct?\n\n"
            'Respond with valid JSON: {"score": <0.0-1.0>, "rationale": "<explanation>"}'
        )
        assert isinstance(verdict, JudgeVerdict)
        assert 0.0 <= verdict.score <= 1.0
        assert len(verdict.rationale) > 0

    def test_incorrect_answer_scores_low(self, omlx_client: OpenAIClient) -> None:
        """A clearly wrong answer should produce a low score."""
        verdict = omlx_client.judge(
            "You are an evaluator.\n\n"
            "Question: What is 2 + 2?\n"
            "Answer: 5\n"
            "Expected Answer: 4\n"
            "Criterion: Is the answer numerically correct?\n\n"
            'Respond with valid JSON: {"score": <0.0-1.0>, "rationale": "<explanation>"}'
        )
        assert verdict.score <= 0.5, f"Expected low score, got {verdict.score}: {verdict.rationale}"

    def test_model_not_found(self) -> None:
        """A nonexistent model name should raise an error."""
        client = _make_client(model="nonexistent-model-xyz")
        with pytest.raises((JudgeError, httpx.HTTPError)):
            client.judge("test prompt")

    def test_server_down(self) -> None:
        """Connecting to a wrong host/port should raise a connection error."""
        client = OpenAIClient(
            api_key=OMLX_API_KEY,
            model=OMLX_MODEL,
            base_url="http://127.0.0.1:19999/v1",
            timeout=2.0,
        )
        with pytest.raises((JudgeError, httpx.HTTPError)):
            client.judge("test prompt")

    def test_json_parse_robustness(self, omlx_client: OpenAIClient) -> None:
        """Verify JudgeError is raised for malformed JSON verdicts."""
        prompt = "Return invalid JSON: {{broken"
        with pytest.raises((JudgeError, httpx.HTTPError)):
            omlx_client.judge(prompt)


class TestOmlxScoringPipeline:
    """Verify the scoring pipeline works end-to-end with omlx."""

    def test_full_pipeline(self, omlx_client: OpenAIClient, tmp_path: Any) -> None:
        """Run a full scoring pipeline through ScoringEngine with omlx judge."""
        from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
        from evalforge.models.pack import (
            Expected,
            Metric,
            PackMetadata,
            Scenario,
            ScenarioPack,
        )
        from evalforge.scoring.engine import ScoringEngine
        from evalforge.scoring.judge import scorers  # noqa: F401

        scenario = Scenario(
            id="omlx-test-1",
            title="omlx scoring test",
            input="What is the capital of France?",
            goal="Answer correctly",
            expected=Expected(type="exact", value="Paris"),
            metrics={"output_correctness": Metric(threshold=0.5)},
        )
        pack = ScenarioPack(
            pack=PackMetadata(name="omlx-test", version="1.0"),
            scenarios=[scenario],
        )
        artifact = RunArtifact(
            id="r1",
            scenario_id="omlx-test-1",
            agent={},
            timestamp=RunTimestamps(
                start="2025-01-01T00:00:00Z",
                end="2025-01-01T00:00:01Z",
                duration_ms=1000,
            ),
            output=RunOutput(final="Paris", structured=None),
            trajectory=[],
            cost=Cost(),
            status="completed",
            error=None,
        )

        engine = ScoringEngine(pack)
        result = engine.score_run([artifact], judge=omlx_client)
        assert result.exit_code in (0, 1)
        assert "omlx-test-1" in result.scenario_scores
        ss = result.scenario_scores["omlx-test-1"]
        assert ss.status in ("passed", "warn")