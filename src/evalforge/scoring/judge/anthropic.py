"""Anthropic Messages API judge client."""

from __future__ import annotations

import httpx

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.openai import _parse_verdict
from evalforge.scoring.result import JudgeVerdict


class AnthropicClient(JudgeClient):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514",
                 timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def judge(self, prompt: str, *, max_tokens: int = 512,
              temperature: float = 0.0) -> JudgeVerdict:
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
