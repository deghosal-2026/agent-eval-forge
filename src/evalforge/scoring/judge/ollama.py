"""Ollama local judge client (OpenAI-compatible API).

Uses Ollama's native chat API endpoint (``/api/chat``) to evaluate agent
outputs via locally hosted models. Supports any model available in the local
Ollama instance (e.g. llama3.2, mistral, qwen).

Verdict parsing reuses the shared :func:`evalforge.scoring.judge.openai._parse_verdict`
function since Ollama's response format includes the content string which is
expected to be valid JSON.
"""

from __future__ import annotations

import httpx

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.openai import _parse_verdict
from evalforge.scoring.result import JudgeVerdict


class OllamaClient(JudgeClient):
    """Judge client using Ollama's local chat API.

    Args:
        model: The Ollama model name (e.g. ``"llama3.2"``, ``"mistral"``).
        base_url: Base URL of the local Ollama server (default
            ``http://localhost:11434``).
        timeout: HTTP request timeout in seconds.
    """
    name = "ollama"

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        """Send a prompt to Ollama's chat API and parse the verdict.

        Uses Ollama's ``/api/chat`` endpoint with ``stream=False``. The
        response content is expected to be a JSON string containing ``score``
        and ``rationale`` fields.

        Args:
            prompt: The evaluation prompt.
            max_tokens: Maximum tokens in the response (mapped to
                ``options.num_predict``).
            temperature: Sampling temperature.

        Returns:
            A JudgeVerdict with score and rationale.

        Raises:
            JudgeError: If the API returns a non-200 status.
        """
        resp = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"num_predict": max_tokens, "temperature": temperature},
                "stream": False,
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise JudgeError(f"Ollama API error {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        content = body.get("message", {}).get("content", "")
        return _parse_verdict(content)
