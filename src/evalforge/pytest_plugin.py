"""Pytest plugin for EvalForge — run scenarios as pytest tests.

Allows developers to run EvalForge scenario packs as native pytest tests,
with automatic parametrization over scenarios, tag filtering, and injected
fixtures for agent configuration and adapter instances.

**Usage via CLI:**

.. code-block:: bash

    pytest --evalforge-pack scenarios/core-launch.yaml \\
           --evalforge-agent python:my_agent.run \\
           --evalforge-judge mock

**Usage via marker:**

.. code-block:: python

    # conftest.py
    pytest_plugins = ["evalforge.pytest_plugin"]

    # test_my_agent.py
    import pytest

    @pytest.mark.evalforge(pack="scenarios/core-launch.yaml")
    def test_agent_runs_scenario(scenario, agent_adapter):
        artifact = agent_adapter.run(scenario, {"run_id": scenario.id})
        assert artifact.status == "completed"

**Available fixtures:**

- ``scenario`` — Parametrized over scenarios in the pack (requires marker).
- ``agent_config`` — Parsed agent config dict from CLI or marker.
- ``agent_adapter`` — Instantiated adapter from the agent config.
- ``scenario_pack`` — The loaded ``ScenarioPack`` from CLI or marker.
"""

from __future__ import annotations

from typing import Any

import pytest

from evalforge.cli.util import parse_agent_spec
from evalforge.loading.pack_loader import load_pack
from evalforge.runner import generate_run_id


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register EvalForge command-line options with pytest."""
    group = parser.getgroup("evalforge")
    group.addoption(
        "--evalforge-pack",
        type=str,
        help="Path to a scenario pack for EvalForge tests",
    )
    group.addoption(
        "--evalforge-agent",
        type=str,
        help="Agent spec for EvalForge tests (e.g. 'python:my_module.run')",
    )
    group.addoption(
        "--evalforge-judge",
        type=str,
        default=None,
        help="Judge spec for EvalForge tests (e.g. 'openai:gpt-4o-mini')",
    )
    group.addoption(
        "--evalforge-tags",
        type=str,
        default=None,
        help="Comma-separated tag filter for EvalForge tests",
    )
    group.addoption(
        "--evalforge-output",
        type=str,
        default=".evalforge",
        help="Output directory for EvalForge artifacts",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register EvalForge markers for documentation and warning suppression."""
    config.addinivalue_line(
        "markers",
        "evalforge(pack=None, agent=None): mark test to run with EvalForge scenarios. "
        "If pack is provided, parametrize over scenarios in that pack.",
    )
    config.addinivalue_line(
        "markers",
        "evalforge_tags(tag1, tag2, ...): "
        "filter scenarios by tags. "
        "Use with @pytest.mark.evalforge(pack=...).",
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize tests over scenarios when the ``scenario`` fixture is requested.

    If a test requests a ``scenario`` parameter, this hook:

    1. Looks for an ``@pytest.mark.evalforge(pack=...)`` marker.
    2. Falls back to the ``--evalforge-pack`` CLI option.
    3. Optionally filters by ``@pytest.mark.evalforge_tags(...)`` or
       ``--evalforge-tags`` CLI option.
    4. Parametrizes the test with one parametrization per matching scenario.

    The scenario objects are instances of ``evalforge.models.pack.Scenario``.
    """
    if "scenario" not in metafunc.fixturenames:
        return

    # Resolve pack path from marker or CLI option
    marker = metafunc.definition.get_closest_marker("evalforge")
    pack_path = marker.kwargs.get("pack") if marker else None
    if not pack_path:
        pack_path = metafunc.config.getoption("--evalforge-pack")
    if not pack_path:
        return

    pack = load_pack(pack_path)

    # Apply optional tag filter from marker or CLI option
    tags_marker = metafunc.definition.get_closest_marker("evalforge_tags")
    tag_filter = metafunc.config.getoption("--evalforge-tags")
    tag_set: set[str] | None = None
    if tags_marker:
        tag_set = set(tags_marker.args)
    elif tag_filter:
        tag_set = set(tag_filter.split(","))

    scenarios = pack.scenarios
    if tag_set:
        scenarios = [s for s in scenarios if tag_set & set(s.tags)]

    ids = [s.id for s in scenarios]
    metafunc.parametrize("scenario", scenarios, ids=ids)


@pytest.fixture
def agent_config(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Provide the parsed agent configuration.

    Resolves from (in priority order):
    1. ``@pytest.mark.evalforge(agent=...)`` marker kwarg.
    2. ``--evalforge-agent`` CLI option.

    Skips the test if neither is provided.
    """
    agent_spec = request.config.getoption("--evalforge-agent")
    if not agent_spec:
        marker = request.node.get_closest_marker("evalforge")
        if marker:
            agent_spec = marker.kwargs.get("agent")
    if not agent_spec:
        pytest.skip(
            "No agent spec provided"
            " (use --evalforge-agent or @pytest.mark.evalforge(agent=...))"
        )

    cfg = parse_agent_spec(agent_spec)
    cfg["run_id"] = generate_run_id()
    return cfg


@pytest.fixture
def agent_adapter(agent_config: dict[str, Any]) -> Any:
    """Provide an instantiated adapter from the agent configuration.

    Depends on ``agent_config``, which will skip the test if no agent spec
    is configured.
    """
    from evalforge.adapters.factory import create_adapter

    return create_adapter(agent_config)


@pytest.fixture
def scenario_pack(request: pytest.FixtureRequest) -> Any:
    """Provide the loaded scenario pack.

    Resolves from (in priority order):
    1. ``@pytest.mark.evalforge(pack=...)`` marker kwarg.
    2. ``--evalforge-pack`` CLI option.

    Skips the test if neither is provided.
    """
    pack_path = request.config.getoption("--evalforge-pack")
    if not pack_path:
        marker = request.node.get_closest_marker("evalforge")
        if marker:
            pack_path = marker.kwargs.get("pack")
    if not pack_path:
        pytest.skip(
            "No pack specified"
            " (use --evalforge-pack or @pytest.mark.evalforge(pack=...))"
        )
    return load_pack(pack_path)
