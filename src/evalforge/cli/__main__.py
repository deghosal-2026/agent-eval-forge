"""Command-line interface for EvalForge.

The CLI is a thin wrapper over the core library (spec §"Runtime Interfaces").
All three surfaces — CLI, pytest plugin, and Python library — share the same
core runner, scorer, and adapter engine; nothing business-logic lives here.

Commands registered:
  - `run`       Run a scenario pack against an agent and score the results.
  - `validate`  Validate packs, agents, and baselines for correctness.
  - `compare`   Compare a candidate run against a golden baseline.
  - `init`      Scaffold a new EvalForge project.
  - `baseline`  Manage golden baselines (save/list/validate/describe/tag/annotate/delete).
  - `cache`     Manage evaluation caches (clear/stats).
  - `plugins`   Discover, list, and inspect plugins.
  - `test`      Run scenario packs as tests with auto-discovery.
  - `benchmark` Import external benchmark datasets as scenario packs.
  - `version`   Print the installed version.
"""

from __future__ import annotations

import click

# Import all subcommand modules; each registers itself on its own Click group
# or top-level command, and is wired into the `main` group below.
from evalforge.cli.baseline import baseline_group
from evalforge.cli.benchmark import benchmark
from evalforge.cli.cache import cache_group
from evalforge.cli.compare import compare
from evalforge.cli.init import init_cmd
from evalforge.cli.plugins import plugins
from evalforge.cli.run import run
from evalforge.cli.test import test_group
from evalforge.cli.validate import validate


@click.group()
def main() -> None:
    """EvalForge — gate agent releases with evidence."""


@main.command()
def version() -> None:
    """Print the installed version."""
    from evalforge import __version__

    click.echo(__version__)


# Wire up all subcommands and command groups under the root `main` group.
main.add_command(run)
main.add_command(validate)
main.add_command(compare)
main.add_command(init_cmd)
main.add_command(baseline_group)
main.add_command(cache_group)
main.add_command(plugins)
main.add_command(test_group)
main.add_command(benchmark)
