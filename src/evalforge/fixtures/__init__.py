"""Fixture system for deterministic agent evaluation.

Provides :class:`ToolStub` and :class:`BrowserToolStub` for intercepting
tool calls with pre-recorded fixture data, enabling fully deterministic
and fast evaluation runs without live services.
"""

from evalforge.fixtures.tool_stub import FixtureNotFoundError, ToolStub

__all__ = ["FixtureNotFoundError", "ToolStub"]
