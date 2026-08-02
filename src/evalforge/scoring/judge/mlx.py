"""mlx-lm judge client for local inference on Apple Silicon.

Uses mlx-lm's OpenAI-compatible local API server. Requires
``mlx-lm`` to be installed (Apple Silicon only).

The server is started on demand via ``mlx_lm.server`` and kept alive for
the duration of the run. The client checks whether a server is already
running on the configured port before starting a new one.

Usage:

    evalforge run --pack scenarios.yaml --agent python:agent.py \\
        --judge mlx:mlx-community/Llama-3.2-3B-Instruct-4bit
"""

from __future__ import annotations

import subprocess
import time

from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.openai import OpenAIClient
from evalforge.scoring.result import JudgeVerdict


class MLXJudgeClient(JudgeClient):
    """Judge client that manages a local mlx-lm server and queries via OpenAI-compatible API.

    The server is started on demand and kept alive for the duration of the run.

    Args:
        model: The mlx-lm model identifier (e.g. ``"Qwen3.5-9B-MLX-4bit"``).
        host: Host address for the server.
        port: Port for the server.
        timeout: HTTP request timeout for judge calls.
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
        self._server_process: subprocess.Popen[bytes] | None = None
        # Type annotation: Popen[bytes] matches the default text=False mode.
        # When text=True is passed, Popen[str] would be correct, but mlx-lm
        # server uses stdout/stderr in binary mode (DEVNULL is type-agnostic).

    def _ensure_server(self) -> str:
        """Start the mlx-lm server if not already running. Returns the base URL.

        Checks if a server is already listening on the configured port. If not,
        spawns ``mlx_lm.server`` as a subprocess and polls the port until it
        becomes available (up to 60 seconds).

        Returns:
            The base URL of the running server (``http://{host}:{port}/v1``).

        Raises:
            RuntimeError: If the server binary is not found or the server
                does not start within the timeout.
        """
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
            self._server_process = subprocess.Popen(  # noqa: S603
                [  # noqa: S607
                    # S607: "mlx_lm.server" is a partial path (no leading / or ./).
                    # This is intentional — mlx-lm registers itself as a CLI entry
                    # point that must be found via PATH. The noqa is accepted because
                    # the user explicitly configured this judge provider and installed
                    # mlx-lm.
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
            ) from None

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        """Send a prompt to the local mlx-lm server.

        Ensures the server is running, then delegates to :class:`OpenAIClient`
        which matches mlx-lm's OpenAI-compatible API protocol.

        Args:
            prompt: The evaluation prompt.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.

        Returns:
            A JudgeVerdict with score and rationale.
        """
        base_url = self._ensure_server()
        client = OpenAIClient(
            api_key="unused",
            model=self.model,
            base_url=base_url,
            timeout=self.timeout,
        )
        return client.judge(prompt, max_tokens=max_tokens, temperature=temperature)

    def __del__(self) -> None:
        """Terminate the mlx-lm server subprocess when the client is garbage collected."""
        if self._server_process:
            self._server_process.terminate()
            self._server_process.wait(timeout=5)
