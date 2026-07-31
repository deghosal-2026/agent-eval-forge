"""Ollama local judge client (OpenAI-compatible API)."""

from __future__ import annotations

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.judge.openai import _parse_verdict
from evalforge.scoring.result import JudgeVerdict


class OllamaClient(JudgeClient):
    name = "ollama"

    def __init__(self, model: str = "llama3.2",
                 base_url: str = "http://localhost:11434",
                 timeout: float = 60.0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def judge(self, prompt: str, *, max_tokens: int = 512,
              temperature: float = 0.0) -> JudgeVerdict:
        import httpx
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
