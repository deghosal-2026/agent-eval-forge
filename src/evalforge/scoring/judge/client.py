"""Judge client abstraction.

Defines the :class:`JudgeClient` abstract base class that all LLM-as-judge
providers must implement. Each provider-specific client (OpenAI, Anthropic,
MLX, Ollama, Mock) subclasses this and provides a ``judge()`` method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from evalforge.models.errors import JudgeError
from evalforge.scoring.result import JudgeVerdict

__all__ = ["JudgeClient", "JudgeError"]


class JudgeClient(ABC):
    """Abstract base class for LLM-as-judge clients.

    Subclasses must set ``name`` to a provider identifier (e.g. ``"openai"``,
    ``"anthropic"``, ``"ollama"``, ``"mlx"``) and implement :meth:`judge`.

    Attributes:
        name: Provider identifier used for logging and cache keying.
    """
    name: str = ""

    @abstractmethod
    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict:
        """Send a prompt to the judge LLM and return a verdict.

        Args:
            prompt: The evaluation prompt, typically constructed by
                :func:`evalforge.scoring.judge.scorers._build_prompt`.
            max_tokens: Maximum tokens in the judge's response.
            temperature: Sampling temperature (0.0 for deterministic output).

        Returns:
            A JudgeVerdict with a score in [0.0, 1.0] and a rationale string.

        Raises:
            JudgeError: If the API call fails or the response is malformed.
        """
        ...
