"""``evalforge baseline`` — manage golden baselines for regression comparison.

A baseline is a snapshot of accepted run artifacts for a scenario pack at a
point in time. It serves as the "truth" against which future candidate runs
are compared to detect regressions.

Subcommands:

- **save** — Create a baseline from a completed run directory.
- **list** — List all saved baselines with metadata.
- **validate** — Check a baseline's integrity and version compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
from evalforge.loading.pack_loader import load_pack
from evalforge.models.artifact import RunArtifact

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
    creation date in a formatted table.
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
