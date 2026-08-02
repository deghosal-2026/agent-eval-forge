"""OpenAI-compatible judge client (also serves local Ollama/LiteLLM with OpenAI protocol).

Uses the OpenAI Chat Completions API (or any compatible endpoint) to evaluate
agent outputs. Supports any model available through an OpenAI-compatible API
including local servers (Ollama, LiteLLM, vLLM) when configured with a
custom ``base_url``.

The response is expected to be valid JSON with ``score`` and ``rationale``
fields. Also handles non-standard response formats from local models (e.g.
bare floats, single-element lists).
"""

from __future__ import annotations

import json

import httpx

from evalforge.models.errors import JudgeError
from evalforge.scoring.judge.client import JudgeClient
from evalforge.scoring.result import JudgeVerdict


class OpenAIClient(JudgeClient):
    """Judge client using the OpenAI Chat Completions API.

    Args:
        api_key: OpenAI API key (or any key for compatible endpoints).
        model: Model identifier (e.g. ``"gpt-4o-mini"``, ``"gpt-4o"``).
        base_url: Base URL for the API. Defaults to OpenAI's endpoint.
            Set to a local server URL for Ollama/LiteLLM compatibility.
        timeout: HTTP request timeout in seconds.
    """
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
        """Send a prompt to the OpenAI-compatible API and parse the verdict.

        Uses ``response_format: json_object`` to request structured JSON output.
        The response is parsed via :func:`_parse_verdict` which handles several
        non-standard response formats from local models.

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

    Also handles:
    - Single-element lists of numbers (e.g. ``[0.9]`` → ``{"score": 0.9}``).
    - Single-element lists of dicts (e.g. ``[{"score": 0.9}]`` → unwrap).

    Args:
        content: The raw JSON string from the model response.

    Returns:
        A JudgeVerdict with the parsed score and rationale.

    Raises:
        JudgeError: If the content is not valid JSON or the score is non-numeric.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"malformed verdict JSON: {exc}") from exc

    # Tolerate non-object verdicts from some local models (e.g., [0.9])
    if not isinstance(data, dict):
        # Single-number list → treat as score
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], int | float):
            data = {"score": float(data[0])}
        # Single-dict list → unwrap
        elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            data = data[0]
        else:
            raise JudgeError(f"expected JSON object, got {type(data).__name__}: {content[:200]}")

    # omlx/Qwen compatibility: unwrap nested response_format wrapper
    if "output" in data and isinstance(data["output"], dict):
        inner = data["output"]
        if "score" in inner:
            data = inner

    score = data.get("score", 0.0)
    if not isinstance(score, int | float):
        raise JudgeError(f"verdict score must be numeric: {score!r}")
    score = max(0.0, min(1.0, float(score)))
    rationale = data.get("rationale", "")
    return JudgeVerdict(score=score, rationale=str(rationale))
