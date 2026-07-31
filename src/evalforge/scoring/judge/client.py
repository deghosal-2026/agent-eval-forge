"""Judge client abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from evalforge.models.errors import JudgeError
from evalforge.scoring.result import JudgeVerdict

__all__ = ["JudgeClient", "JudgeError"]


class JudgeClient(ABC):
    name: str = ""

    @abstractmethod
    def judge(
        self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0
    ) -> JudgeVerdict: ...
