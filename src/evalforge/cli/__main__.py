"""Command-line interface for EvalForge.

The CLI is a thin wrapper over the core library (spec §"Runtime Interfaces").
All three surfaces — CLI, pytest plugin, and Python library — share the same
core runner, scorer, and adapter engine; nothing business-logic lives here.

This module only defines the command group and the `version` command. The
full command surface (`run`, `validate`, `compare`, `baseline`, ...) lands in
M7. Each future command registers via the `@main.command()` decorator so the
group stays extensible without centralizing dispatch.
"""

import click


@click.group()
def main() -> None:
    """EvalForge — gate agent releases with evidence.

    The root group carries no behavior of its own; it exists to namespace
    subcommands and share click options. Command bodies delegate to the core
    runner / scorer / compare modules so behavior is identical whether invoked
    from the shell, pytest, or the library API.
    """


@main.command()
def version() -> None:
    """Print the installed version.

    Useful as a smoke test that the package is importable and the console
    entry point is wired correctly (used by CI and by `pip install -e .`
    verification). The import is deferred to function scope so `evalforge
    --help` and other lightweight commands never pay the cost of importing
    the full package, and so a broken import fails loudly only on the
    commands that actually need the library.
    """
    from evalforge import __version__

    click.echo(__version__)
