"""OpenAI-compatible judge client (also serves local Ollama/LiteLLM with openai prot)."""

from __future__ import annotations

import json

import httpx

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.result import JudgeVerdict


class OpenAIClient(JudgeClient):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise JudgeError(f"OpenAI API error {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        return _parse_verdict(content)


def _parse_verdict(content: str) -> JudgeVerdict:
    """Parse a JSON verdict string, clamping score to [0,1].

    Some models (e.g. Qwen via omlx) nest the verdict under an ``output`` key
    when ``response_format: json_object`` is used.  The unwrapping handles that
    transparently so callers don't need to know about model-specific wrappers.

    The unwrapping is conservative: it only redirects if the inner dict has a
    ``score`` key, so a legitimate top-level ``output`` field in the verdict
    schema is not discarded.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"malformed verdict JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise JudgeError(f"expected JSON object, got {type(data).__name__}: {content[:200]}")

    # omlx/Qwen compatibility: unwrap nested response_format wrapper
    if "output" in data and isinstance(data["output"], dict):
        inner = data["output"]
        if "score" in inner:
            data = inner

    score = data.get("score", 0.0)
    if not isinstance(score, (int, float)):
        raise JudgeError(f"verdict score must be numeric: {score!r}")
    score = max(0.0, min(1.0, float(score)))
    rationale = data.get("rationale", "")
    return JudgeVerdict(score=score, rationale=str(rationale))
