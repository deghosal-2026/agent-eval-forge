"""Tests for the mlx judge client (Apple Silicon only)."""

from __future__ import annotations

from evalforge.scoring.judge.mlx import MLXJudgeClient


class TestMLXJudgeClientContract:
    """Verifies MLXJudgeClient follows the JudgeClient protocol."""

    def test_is_judge_client(self) -> None:
        j = MLXJudgeClient(model="test-model")
        assert j.name == "mlx"

    def test_model_accepts_hf_path(self) -> None:
        j = MLXJudgeClient(model="Qwen3.5-9B-MLX-4bit")
        assert "Qwen" in j.model

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