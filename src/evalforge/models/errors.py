"""Error hierarchy for EvalForge.

Every EvalForge-specific exception derives from :class:`EvalForgeError` so
callers can catch one base type without leaking framework exceptions into
public APIs. Location-aware errors (:class:`PackParseError`) carry an optional
``file``/``line`` pair that render as ``file:line: message`` when both are
present, which is what makes loader diagnostics actionable.
"""

from __future__ import annotations


class EvalForgeError(Exception):
    """Base class for all EvalForge errors."""


class PackParseError(EvalForgeError):
    """A scenario pack could not be parsed or validated.

    Args:
        message: Human-readable description of the failure.
        file: Path of the offending pack file, if known.
        line: 1-based line number where the problem occurred, if known.
    """

    def __init__(self, message: str, file: str | None = None, line: int | None = None) -> None:
        self.file = file
        self.line = line
        if file is not None and line is not None:
            rendered = f"{file}:{line}: {message}"
        else:
            rendered = message
        super().__init__(rendered)


class AdapterError(EvalForgeError):
    """An agent adapter failed to invoke or normalize a run."""


class AgentTimeoutError(AdapterError):
    """The agent exceeded its timeout budget."""
