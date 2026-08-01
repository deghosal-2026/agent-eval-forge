"""mlx-lm judge client for local inference on Apple Silicon.

Uses mlx-lm's OpenAI-compatible local API server. Requires
``mlx-lm`` to be installed (Apple Silicon only).

Usage:

    evalforge run --pack scenarios.yaml --agent python:agent.py \\
        --judge mlx:mlx-community/Llama-3.2-3B-Instruct-4bit
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.openai import OpenAIClient
from evalforge.scoring.result import JudgeVerdict


class MLXJudgeClient(JudgeClient):
    """Judge client that manages a local mlx-lm server and queries via OpenAI-compatible API.

    The server is started on demand and kept alive for the duration of the run.
    """

    name = "mlx"

    def __init__(
        self,
        model: str = "Qwen3.5-9B-MLX-4bit",
        host: str = "127.0.0.1",
        port: int = 8080,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.host = host
        self.port = port
        self.timeout = timeout
        self._server_process: subprocess.Popen | None = None

    def _ensure_server(self) -> str:
        """Start the mlx-lm server if not already running. Returns the base URL."""
        # Check if server is already running on the port
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self.host, self.port))
            sock.close()
            return f"http://{self.host}:{self.port}/v1"
        except ConnectionRefusedError:
            pass
        finally:
            sock.close()

        try:
            self._server_process = subprocess.Popen(
                [
                    "mlx_lm.server",
                    "--model", self.model,
                    "--host", self.host,
                    "--port", str(self.port),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for server to be ready
            for _ in range(30):
                time.sleep(2)
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.connect((self.host, self.port))
                    sock.close()
                    return f"http://{self.host}:{self.port}/v1"
                except ConnectionRefusedError:
                    continue
                finally:
                    sock.close()
            raise RuntimeError(f"mlx-lm server did not start within 60s for model {self.model}")
        except FileNotFoundError:
            raise RuntimeError(
                "mlx_lm.server not found. Install with: pip install mlx-lm"
            )

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        base_url = self._ensure_server()
        client = OpenAIClient(
            api_key="unused",
            model=self.model,
            base_url=base_url,
            timeout=self.timeout,
        )
        return client.judge(prompt, max_tokens=max_tokens, temperature=temperature)

    def __del__(self) -> None:
        if self._server_process:
            self._server_process.terminate()
            self._server_process.wait(timeout=5)