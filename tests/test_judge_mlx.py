"""Tests for the mlx judge client (Apple Silicon only)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.mlx import MLXJudgeClient
from evalforge.scoring.result import JudgeVerdict


class TestMLXJudgeClientContract:
    """Verifies MLXJudgeClient follows the JudgeClient protocol."""

    def test_is_judge_client(self) -> None:
        j = MLXJudgeClient(model="test-model")
        assert isinstance(j, JudgeClient)
        assert j.name == "mlx"

    def test_model_accepts_hf_path(self) -> None:
        j = MLXJudgeClient(model="Qwen3.5-9B-MLX-4bit")
        assert j.model == "Qwen3.5-9B-MLX-4bit"

    def test_defaults(self) -> None:
        j = MLXJudgeClient()
        assert j.model == "Qwen3.5-9B-MLX-4bit"
        assert j.host == "127.0.0.1"
        assert j.port == 8080

    def test_port_override(self) -> None:
        j = MLXJudgeClient(port=9090)
        assert j.port == 9090

    def test_model_override(self) -> None:
        j = MLXJudgeClient(model="custom-model")
        assert j.model == "custom-model"

    def test_judge_calls_openai_client(self) -> None:
        j = MLXJudgeClient(model="test-model")
        mock_verdict = JudgeVerdict(score=0.85, rationale="looks correct")
        with (
            patch.object(j, "_ensure_server", return_value="http://127.0.0.1:8080/v1"),
            patch(
                "evalforge.scoring.judge.mlx.OpenAIClient",
            ) as mock_openai_cls,
        ):
            mock_openai = mock_openai_cls.return_value
            mock_openai.judge.return_value = mock_verdict
            result = j.judge("test prompt", max_tokens=256, temperature=0.2)
            assert result.score == 0.85
            assert result.rationale == "looks correct"
            mock_openai_cls.assert_called_once_with(
                api_key="unused",
                model="test-model",
                base_url="http://127.0.0.1:8080/v1",
                timeout=120.0,
            )
            mock_openai.judge.assert_called_once_with(
                "test prompt", max_tokens=256, temperature=0.2,
            )

    def test_judge_ensures_server_on_each_call(self) -> None:
        j = MLXJudgeClient(model="test-model")
        mock_verdict = JudgeVerdict(score=0.5, rationale="ok")
        with (
            patch.object(j, "_ensure_server", return_value="http://127.0.0.1:8080/v1"),
            patch("evalforge.scoring.judge.mlx.OpenAIClient") as mock_openai_cls,
        ):
            mock_openai = mock_openai_cls.return_value
            mock_openai.judge.return_value = mock_verdict
            j.judge("first call")
            j.judge("second call")
            assert j._ensure_server.call_count == 2  # type: ignore[attr-defined]


class TestMLXJudgeClientServerLifecycle:
    """Tests for the _ensure_server method and error handling."""

    def test_ensure_server_raises_on_missing_mlx_lm(self) -> None:
        j = MLXJudgeClient(model="test-model")
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="mlx_lm.server not found"):
                j._ensure_server()

    def test_ensure_server_raises_on_startup_timeout(self) -> None:
        j = MLXJudgeClient(model="test-model")
        mock_popen = MagicMock()
        with (
            patch("subprocess.Popen", return_value=mock_popen),
            patch("time.sleep"),
            patch("socket.socket") as mock_socket_cls,
        ):
            mock_sock = mock_socket_cls.return_value
            mock_sock.connect.side_effect = ConnectionRefusedError
            with pytest.raises(RuntimeError, match="did not start within 60s"):
                j._ensure_server()

    def test_ensure_server_starts_process_with_correct_args(self) -> None:
        j = MLXJudgeClient(model="custom-model", host="0.0.0.0", port=9999)  # noqa: S104
        mock_popen = MagicMock()
        with (
            patch("subprocess.Popen", return_value=mock_popen) as mock_popen_fn,
            patch("time.sleep"),
            patch("socket.socket") as mock_socket_cls,
        ):
            mock_sock = mock_socket_cls.return_value
            mock_sock.connect.side_effect = [ConnectionRefusedError, None]
            result = j._ensure_server()
            assert result == "http://0.0.0.0:9999/v1"
            mock_popen_fn.assert_called_once_with(
                [
                    "mlx_lm.server",
                    "--model", "custom-model",
                    "--host", "0.0.0.0",  # noqa: S104
                    "--port", "9999",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def test_ensure_server_skips_start_when_already_running(self) -> None:
        j = MLXJudgeClient(model="test-model")
        with (
            patch("subprocess.Popen") as mock_popen_fn,
            patch("socket.socket") as mock_socket_cls,
        ):
            mock_sock = mock_socket_cls.return_value
            mock_sock.connect.return_value = None
            result = j._ensure_server()
            assert result == "http://127.0.0.1:8080/v1"
            mock_popen_fn.assert_not_called()
