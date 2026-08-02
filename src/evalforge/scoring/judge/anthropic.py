"""Anthropic Messages API judge client.

Uses the Anthropic Messages API to evaluate agent outputs via Claude models.
The system prompt instructs Claude to respond with valid JSON containing
``score`` and ``rationale`` fields. Verdict parsing is delegated to the shared
:func:`evalforge.scoring.judge.openai._parse_verdict` function since both
providers produce the same JSON schema.
"""

from __future__ import annotations

import httpx

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.openai import _parse_verdict
from evalforge.scoring.result import JudgeVerdict


class AnthropicClient(JudgeClient):
    """Judge client using the Anthropic Messages API.

    Args:
        api_key: Anthropic API key.
        model: Claude model identifier (default ``"claude-sonnet-4-20250514"``).
        timeout: HTTP request timeout in seconds.
    """
    name = "anthropic"

    def __init__(
        self, api_key: str, model: str = "claude-sonnet-4-20250514", timeout: float = 30.0
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        """Send a prompt to the Anthropic Messages API and parse the verdict.

        The system message instructs Claude to respond with a JSON object
        containing ``score`` (0.0-1.0) and ``rationale``. The response text
        is parsed via the shared ``_parse_verdict`` function.

        Args:
            prompt: The evaluation prompt.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.

        Returns:
            A JudgeVerdict with score and rationale.

        Raises:
            JudgeError: If the API returns a non-200 status or the response
                cannot be parsed.
        """
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": "You are a judge. Respond with valid JSON: "
                '{"score": 0.0-1.0, "rationale": "..."}',
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise JudgeError(f"Anthropic API error {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        content = body["content"][0]["text"]
        return _parse_verdict(content)
