"""Shared pytest fixtures for EvalForge tests.

Fixtures defined here are available to every test in the suite without an
explicit import. Keep the set small: fixtures that are only needed by one
test module belong in that module's `conftest.py` (or inline), not here.

`tmp_project` is a thin, named wrapper over pytest's built-in `tmp_path` so
tests read as "working inside a project root" — which matters for anything
that writes `.evalforge/`, `evalforge.toml`, or scenario packs relative to a
cwd. M8's fixture/cache/parallel tests will add to this file.
"""

import sys
from pathlib import Path

import pytest

# Make `tests/fixtures` importable as the top-level package `fixtures` so
# python-import adapter tests can reference mock agents via config
# (`module="fixtures.agents"`). The parent process inserts this path, and
# multiprocessing (spawn) propagates `sys.path` to child processes.
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temporary directory representing a project root.

    Pytest guarantees a fresh directory per test, so tests cannot leak state
    into each other or into the real checkout.
    """
    return tmp_path


@pytest.fixture
def llm_vcr(tmp_path: Path):
    """Fixture providing LLM VCR for record/replay tests."""
    from evalforge.testing.vcr import LLMVCR

    cassettes_dir = tmp_path / "cassettes"
    cassettes_dir.mkdir()
    yield LLMVCR(cassette_dir=str(cassettes_dir))


@pytest.fixture
def mocked_llm_profile(monkeypatch: pytest.MonkeyPatch):
    """Fixture that toggles mocked LLM mode for CI.

    Sets EVALFORGE_MOCK_LLM=1 so that any LLM calls fall back to mock
    responses without hitting real providers.
    """
    monkeypatch.setenv("EVALFORGE_MOCK_LLM", "1")
    yield
    monkeypatch.delenv("EVALFORGE_MOCK_LLM", raising=False)
