"""Command-line interface for EvalForge.

The CLI is a thin wrapper over the core library (spec §"Runtime Interfaces").
All three surfaces — CLI, pytest plugin, and Python library — share the same
core runner, scorer, and adapter engine; nothing business-logic lives here.
"""

from __future__ import annotations

import click

from evalforge.cli.baseline import baseline_group
from evalforge.cli.cache import cache_group
from evalforge.cli.compare import compare
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


main.add_command(run)
main.add_command(validate)
main.add_command(compare)
main.add_command(baseline_group)
main.add_command(cache_group)
main.add_command(plugins)
main.add_command(test_group)
