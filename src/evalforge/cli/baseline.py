"""``evalforge baseline`` — manage golden baselines for regression comparison.

A baseline is a snapshot of accepted run artifacts for a scenario pack at a
point in time. It serves as the "truth" against which future candidate runs
are compared to detect regressions.

Subcommands:

- **save** — Create a baseline from a completed run directory.
- **list** — List all saved baselines with metadata.
- **validate** — Check a baseline's integrity and version compatibility.
- **describe** — Show detailed information about a baseline.
- **tag** — Add tags to a baseline.
- **annotate** — Add notes to a baseline.
- **delete** — Delete a baseline.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
from evalforge.loading.pack_loader import load_pack
from evalforge.models.artifact import RunArtifact

console = Console()

# The baseline command group — registered as a subcommand of ``main``
baseline_group = click.Group(
    name="baseline",
    help="Manage golden baselines for regression comparison.",
)


@baseline_group.command("save")
@click.option("--name", required=True, help="Baseline name (e.g. v1.0.0)")
@click.option(
    "--run",
    required=True,
    help="Path to the completed run directory (e.g. .evalforge/runs/run-...)",
)
@click.option(
    "--pack",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Scenario pack used for the run",
)
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_save(name: str, run: str, pack: str, output_dir: str) -> None:
    r"""Save a golden baseline from a completed run.

    Reads the artifacts from the run directory, validates them against the
    scenario pack, and persists them as a named baseline in the baseline
    store (default: ``.evalforge/baselines/<name>.json``).

    The baseline captures:
    - All ``RunArtifact``\ s from the run (one per scenario).
    - Pack metadata (name, version) for later compatibility checks.
    - Agent metadata (sanitized, no API keys).
    - Git SHA and creation timestamp for traceability.

    Args:
        name: Name for the baseline (e.g. "v1.0.0").
        run: Path to the completed run directory containing artifacts.
        pack: Path to the scenario pack used for the run.
        output_dir: Base output directory for the baseline store.

    Exits with:
        0 on success, 1 if the run or artifact directory is missing.
    """
    # Load the pack to get metadata and validate the run's artifacts
    scenario_pack = load_pack(pack)

    run_dir = Path(run)
    if not run_dir.exists():
        click.echo(f"Error: run directory not found: {run}", err=True)
        raise SystemExit(1)

    artifact_dir = run_dir / "artifacts"
    if not artifact_dir.exists():
        click.echo(
            f"Error: no artifacts found in {run}/artifacts", err=True
        )
        raise SystemExit(1)

    # Load all artifact JSON files from the run directory
    artifacts: list[RunArtifact] = []
    for af in sorted(artifact_dir.glob("*.json")):
        artifacts.append(RunArtifact(**json.loads(af.read_text())))

    # Construct the baseline from the pack metadata and run artifacts
    baseline_obj = Baseline(
        name=name,
        pack=scenario_pack.pack.name,
        pack_version=scenario_pack.pack.version,
        runs=artifacts,
    )

    # Persist to disk
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    store.save(baseline_obj)
    click.echo(f"Baseline '{name}' saved ({len(artifacts)} scenarios)")


@baseline_group.command("list")
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_list(output_dir: str) -> None:
    """List all saved baselines with metadata.

    Displays each baseline's name, pack, version, scenario count, and
    creation date in a formatted list.

    Args:
        output_dir: Base output directory for the baseline store.
    """
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    names = store.list()

    if not names:
        click.echo("No baselines found")
        return

    # Load each baseline to display its metadata
    for name in names:
        bl = store.load(name)
        click.echo(
            f"  {bl.name:20s} pack={bl.pack:30s} v{bl.pack_version:8s}"
            f"  {len(bl.runs):2d} scenarios  {bl.created[:10]}"
        )


@baseline_group.command("validate")
@click.option("--baseline", required=True, help="Name of the baseline to validate")
@click.option(
    "--pack",
    type=click.Path(exists=True, dir_okay=False),
    help="Scenario pack to validate against (checks version compatibility)",
)
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_validate(baseline: str, pack: str | None, output_dir: str) -> None:
    """Validate a baseline's integrity and version compatibility.

    Checks:
    1. The baseline file exists and is valid JSON.
    2. All required fields are present (name, pack, version, runs, etc.).
    3. If ``--pack`` is provided, verifies the baseline's pack name and
       version match the current pack (warns on mismatch).

    Args:
        baseline: Name of the baseline to validate.
        pack: Optional path to a scenario pack to check compatibility.
        output_dir: Base output directory for the baseline store.
    """
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    try:
        bl = store.load(baseline)
    except FileNotFoundError:
        click.echo(f"Error: baseline '{baseline}' not found", err=True)
        raise SystemExit(1) from None

    warnings: list[str] = []

    # Check version compatibility with the current pack
    if pack:
        pack_meta = load_pack(pack).pack
        if bl.pack != pack_meta.name:
            warnings.append(
                f"pack name mismatch:"
                f" baseline='{bl.pack}' vs pack='{pack_meta.name}'",
            )
        if bl.pack_version != pack_meta.version:
            warnings.append(
                f"pack version mismatch:"
                f" baseline='{bl.pack_version}' vs pack='{pack_meta.version}'",
            )

    click.echo(
        f"Baseline '{bl.name}': {len(bl.runs)} scenarios,"
        f" pack={bl.pack} v{bl.pack_version}"
    )
    if warnings:
        for w in warnings:
            click.echo(f"  Warning: {w}")
    else:
        click.echo("  All checks passed")


@baseline_group.command("describe")
@click.argument("name")
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_describe(name: str, output_dir: str) -> None:
    """Show detailed information about a baseline.

    Displays name, pack, version, scenario count, average score, tags,
    notes, trust level, git SHA, and creation date in a formatted panel.

    Args:
        name: Baseline name to describe.
        output_dir: Base output directory for the baseline store.
    """
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    try:
        info = store.describe(name)
    except FileNotFoundError:
        click.echo(f"Error: baseline '{name}' not found", err=True)
        raise SystemExit(1) from None

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")

    table.add_row("Name", info["name"])
    table.add_row("Pack", info["pack"])
    table.add_row("Version", info["pack_version"])
    table.add_row("Scenarios", str(info["scenarios"]))
    if info["avg_score"] is not None:
        table.add_row("Avg Score", f"{info['avg_score']:.2f}")
    else:
        table.add_row("Avg Score", "[dim]N/A[/dim]")

    tags_str = ", ".join(info["tags"]) if info["tags"] else "[dim]none[/dim]"
    table.add_row("Tags", tags_str)

    notes_str = info["notes"] if info["notes"] else "[dim]none[/dim]"
    table.add_row("Notes", notes_str)

    trust_style = "green" if info["trust"] == "local" else "yellow"
    table.add_row("Trust", f"[{trust_style}]{info['trust']}[/{trust_style}]")

    git_str = info["git_sha"] if info["git_sha"] else "[dim]unknown[/dim]"
    table.add_row("Git SHA", git_str)
    table.add_row("Created", info["created"])

    console.print(Panel(table, title=f"Baseline: {name}", border_style="blue"))


@baseline_group.command("tag")
@click.argument("name")
@click.argument("tags", nargs=-1, required=True)
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_tag(name: str, tags: tuple[str, ...], output_dir: str) -> None:
    """Add tags to a baseline.

    Tags are replaced entirely (not appended). Pass one or more space-separated
    tag values.

    Args:
        name: Baseline name to tag.
        tags: One or more tag strings to set on the baseline.
        output_dir: Base output directory for the baseline store.
    """
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    try:
        bl = store.tag(name, list(tags))
    except FileNotFoundError:
        click.echo(f"Error: baseline '{name}' not found", err=True)
        raise SystemExit(1) from None

    click.echo(f"Tags updated for baseline '{name}': {', '.join(bl.tags)}")


@baseline_group.command("annotate")
@click.argument("name")
@click.argument("notes")
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_annotate(name: str, notes: str, output_dir: str) -> None:
    """Add notes to a baseline.

    Notes are replaced entirely (not appended).

    Args:
        name: Baseline name to annotate.
        notes: Note text to set on the baseline.
        output_dir: Base output directory for the baseline store.
    """
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    try:
        store.annotate(name, notes)
    except FileNotFoundError:
        click.echo(f"Error: baseline '{name}' not found", err=True)
        raise SystemExit(1) from None

    click.echo(f"Notes updated for baseline '{name}'")


@baseline_group.command("delete")
@click.argument("name")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--output-dir", default=".evalforge", show_default=True,
    help="Output directory for the baseline store",
)
def baseline_delete(name: str, force: bool, output_dir: str) -> None:
    """Delete a baseline.

    Prompts for confirmation unless --force is used.

    Args:
        name: Baseline name to delete.
        force: Skip the confirmation prompt.
        output_dir: Base output directory for the baseline store.
    """
    store = BaselineStore(base_dir=f"{output_dir}/baselines")
    try:
        store.load(name)
    except FileNotFoundError:
        click.echo(f"Error: baseline '{name}' not found", err=True)
        raise SystemExit(1) from None

    if not force:
        confirmed = click.confirm(
            f"Are you sure you want to delete baseline '{name}'?"
        )
        if not confirmed:
            click.echo("Delete cancelled")
            raise SystemExit(0)

    store.delete(name)
    click.echo(f"Baseline '{name}' deleted")
