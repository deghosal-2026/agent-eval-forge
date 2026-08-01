"""Integration tests for the Ollama judge client.

These tests require an Ollama server reachable at the host specified by the
``OLLAMA_HOST`` environment variable.  Skip the file with::

    pytest -m "not ollama"

The default model used for test inference is ``llama3.2``.
"""

from __future__ import annotations

import os
import socket

import pytest

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.ollama import OllamaClient
from evalforge.scoring.result import JudgeVerdict

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost:11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


def _ollama_available() -> bool:
    host, port_str = OLLAMA_HOST.split(":", 1)
    port = int(port_str)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _make_client(model: str = OLLAMA_MODEL) -> OllamaClient:
    return OllamaClient(model=model, base_url=OLLAMA_BASE_URL, timeout=30.0)


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not os.environ.get("OLLAMA_HOST"), reason="OLLAMA_HOST not set"),
]


@pytest.fixture(scope="module")
def ollama_client() -> OllamaClient:
    if not _ollama_available():
        pytest.skip(f"Ollama server not reachable at {OLLAMA_BASE_URL}")
    return _make_client()


class TestOllamaJudgeVerdicts:
    """Verify the Ollama judge returns valid JudgeVerdict responses."""

    def test_happy_path(self, ollama_client: OllamaClient) -> None:
        """Call judge with a valid prompt and get a properly structured verdict."""
        verdict = ollama_client.judge(
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

    def test_incorrect_answer_scores_low(self, ollama_client: OllamaClient) -> None:
        """A clearly wrong answer should produce a low score."""
        verdict = ollama_client.judge(
            "You are an evaluator.\n\n"
            "Question: What is 2 + 2?\n"
            "Answer: 5\n"
            "Expected Answer: 4\n"
            "Criterion: Is the answer numerically correct?\n\n"
            'Respond with valid JSON: {"score": <0.0-1.0>, "rationale": "<explanation>"}'
        )
        assert verdict.score <= 0.5, f"Expected low score, got {verdict.score}: {verdict.rationale}"

    def test_model_not_found(self) -> None:
        """A nonexistent model name should raise JudgeError."""
        client = _make_client(model="nonexistent-model-xyz")
        with pytest.raises(JudgeError):
            client.judge("test prompt")

    def test_server_down(self) -> None:
        """Connecting to a wrong host/port should raise a connection error."""
        client = OllamaClient(base_url="http://127.0.0.1:19999", timeout=2.0)
        with pytest.raises(JudgeError):
            client.judge("test prompt")

    def test_json_parse_robustness(self) -> None:
        """Verify JudgeError is raised for malformed JSON verdicts."""
        client = _make_client()
        prompt = "Return invalid JSON: {{broken"
        with pytest.raises(JudgeError):
            client.judge(prompt)


class TestOllamaScoringPipeline:
    """Verify the scoring pipeline works end-to-end with Ollama."""

    def test_full_pipeline(self, ollama_client: OllamaClient, tmp_path) -> None:
        """Run a full scoring pipeline through ScoringEngine with an Ollama judge."""
        from evalforge.models.artifact import RunArtifact, RunOutput, RunTimestamps, Cost
        from evalforge.models.pack import Metric, Scenario, ScenarioPack, Expected, PackMetadata
        from evalforge.scoring.engine import ScoringEngine

        scenario = Scenario(
            id="ollama-test-1",
            title="Ollama scoring test",
            input="What is the capital of France?",
            goal="Answer correctly",
            expected=Expected(type="exact", value="Paris"),
            metrics={"judge_correctness": Metric(threshold=0.5)},
        )
        pack = ScenarioPack(pack=PackMetadata(name="ollama-test", version="1.0"), scenarios=[scenario])
        artifact = RunArtifact(
            id="r1",
            scenario_id="ollama-test-1",
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
        result = engine.score_run([artifact], judge=ollama_client)
        assert result.exit_code in (0, 1)
        assert "ollama-test-1" in result.scenario_scores
        ss = result.scenario_scores["ollama-test-1"]
        assert ss.status in ("passed", "warn")