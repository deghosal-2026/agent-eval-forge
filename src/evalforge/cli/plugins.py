"""``evalforge plugins`` — list registered plugins and custom scorers.

Useful for debugging: verify that built-in and custom scorers are properly
registered and discoverable via the scorer registry.
"""

from __future__ import annotations

import click

from evalforge.scoring.registry import SCORERS


@click.command()
def plugins() -> None:
    """List all registered scorers.

    Displays the name and Python module path of every scorer that has been
    registered via the ``@register_scorer`` decorator or discovered via
    entry points. Use this to verify that custom scorers are loaded correctly.
    """
    click.echo("Registered Scorers:")
    if not SCORERS:
        click.echo("  (none)")
    else:
        for name, cls in sorted(SCORERS.items()):
            click.echo(f"  {name:30s} {cls.__module__}.{cls.__qualname__}")
