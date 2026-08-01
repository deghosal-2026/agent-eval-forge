"""``evalforge validate`` — validate packs, agents, and baselines for correctness.

Pre-flight validation that catches issues early, before a full evaluation run.
Can validate any combination of:

- **Scenario packs**: structural validity, duplicate IDs, known metric names,
  threshold ranges, YAML/JSON parseability.
- **Agent specs**: adapter type recognition, module importability.
- **Baselines**: file existence, version compatibility with the current pack.
- **Fixture coverage**: checks that every tool used in scenarios has a
  corresponding fixture file in ``scenarios/fixtures/``.

All core library imports are deferred to function scope so this command
loads instantly for ``--help``.
"""

from __future__ import annotations

from pathlib import Path

import click

from evalforge.cli.util import parse_agent_spec


@click.command()
@click.option(
    "--pack",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to a scenario pack YAML/JSON file to validate",
)
@click.option(
    "--agent",
    help="Agent spec to validate (e.g. 'python:my_module.run' or './my_agent')",
)
@click.option("--baseline", help="Baseline name to validate")
@click.option(
    "--strict",
    is_flag=True,
    help="Promote warnings to errors (e.g. pack version mismatch → exit 1)",
)
@click.option(
    "--check-fixtures",
    is_flag=True,
    help="Validate that fixture data covers all tools referenced in scenarios",
)
@click.option(
    "--output-dir",
    default=".evalforge",
    show_default=True,
    help="Output directory for baseline store (used with --baseline)",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "markdown", "terminal"]),
    default="terminal",
    show_default=True,
)
@click.option(
    "--pre-flight",
    is_flag=True,
    help="Run all validation checks (pack + agent + baseline + fixtures) in one pass",
)
def validate(
    pack: str | None,
    agent: str | None,
    baseline: str | None,
    strict: bool,
    check_fixtures: bool,
    output_dir: str,
    output_format: str,
    pre_flight: bool = False,
) -> None:
    """Validate packs, agents, and baselines for correctness.

    Provide at least one of ``--pack``, ``--agent``, ``--baseline``,
    or ``--check-fixtures``. Multiple flags can be combined to validate
    everything in one pass.
    """
    # Core imports deferred for fast --help
    from evalforge.adapters.factory import create_adapter
    from evalforge.baselines.store import BaselineStore
    from evalforge.cli.formatter import OutputFormatter
    from evalforge.loading.pack_loader import load_pack

    if pre_flight:
        if not pack:
            default_pack = "scenarios/core-launch.yaml"
            if Path(default_pack).exists():
                pack = default_pack
        if not check_fixtures and Path("scenarios/fixtures").exists():
            check_fixtures = True

    results: dict[str, dict[str, object]] = {}
    all_valid = True

    # Validate scenario pack: structural checks, known metrics, duplicate IDs
    if pack:
        try:
            scenario_pack = load_pack(pack)
            meta = scenario_pack.pack
            scenario_count = len(scenario_pack.scenarios)
            tag_count = (
                len({t for s in scenario_pack.scenarios for t in s.tags})
                if scenario_pack.scenarios
                else 0
            )
            results["pack"] = {
                "valid": True,
                "message": (
                    f"Pack '{meta.name}' v{meta.version}:"
                    f" {scenario_count} scenarios, {tag_count} unique tags"
                ),
                "name": meta.name,
                "version": meta.version,
                "scenarios": scenario_count,
                "tags": tag_count,
                "trust": meta.trust,
            }
        except Exception as e:
            results["pack"] = {"valid": False, "message": str(e)}
            all_valid = False

    # Validate agent spec: adapter type + module importability
    if agent:
        try:
            import importlib

            cfg = parse_agent_spec(agent)
            # For framework adapters, verify the module can be imported
            if cfg["type"] in ("python", "langgraph", "pydantic-ai"):
                importlib.import_module(cfg["module"])
            # Verifies the adapter class can be instantiated
            create_adapter(cfg)
            agent_warnings: list[str] = []
            if cfg["type"] == "http":
                import httpx

                try:
                    r = httpx.head(cfg.get("url", ""), timeout=5)
                    if r.status_code >= 500:
                        agent_warnings.append(
                            f"HTTP endpoint returned {r.status_code}"
                        )
                except Exception as e:
                    agent_warnings.append(f"HTTP connectivity check failed: {e}")
            results["agent"] = {
                "valid": True,
                "message": f"Adapter '{cfg['type']}' created successfully",
                "type": cfg["type"],
                "warnings": agent_warnings,
            }
        except Exception as e:
            results["agent"] = {"valid": False, "message": str(e)}
            all_valid = False

    # Enforce trust policy when both pack and agent are provided
    if results.get("pack", {}).get("valid") and results.get("agent", {}).get("valid"):
        from evalforge.security.policy import TrustLevel, TrustPolicy
        pack_raw = results["pack"].get("trust", "local")
        agent_raw = results["agent"].get("type", "subprocess")
        pack_trust: TrustLevel = pack_raw if isinstance(pack_raw, str) and pack_raw in ("builtin", "local", "external") else "local"  # type: ignore[assignment]
        agent_type: str = agent_raw if isinstance(agent_raw, str) else "subprocess"
        sandbox = False
        policy = TrustPolicy(trust=pack_trust, adapter_type=agent_type, sandbox=sandbox)
        allowed, reason = policy.allowed()
        if not allowed:
            results.setdefault("trust_policy", {})["valid"] = False
            results["trust_policy"]["message"] = reason
            all_valid = False

    # Validate baseline: file exists, version compatibility with pack
    if baseline:
        try:
            store = BaselineStore(base_dir=f"{output_dir}/baselines")
            bl = store.load(baseline)
            warnings: list[str] = []
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
            results["baseline"] = {
                "valid": len(warnings) == 0 or not strict,
                "message": (
                    f"Baseline '{bl.name}':"
                    f" {len(bl.runs)} scenarios, pack={bl.pack} v{bl.pack_version}"
                ),
                "name": bl.name,
                "pack": bl.pack,
                "pack_version": bl.pack_version,
                "runs": len(bl.runs),
                "warnings": warnings,
            }
            if strict and warnings:
                all_valid = False
        except Exception as e:
            results["baseline"] = {"valid": False, "message": str(e)}
            all_valid = False

    # Validate fixture coverage: every tool in scenarios has a fixture file
    if check_fixtures and pack:
        try:
            scenario_pack = load_pack(pack)
            required_tools = {
                t.name for s in scenario_pack.scenarios for t in s.allowed_tools
            }

            fixtures_dir = Path("scenarios/fixtures")
            available_files = (
                {f.stem for f in fixtures_dir.glob("*.json")}
                if fixtures_dir.exists()
                else set()
            )
            missing = required_tools - available_files
            results["fixtures"] = {
                "valid": len(missing) == 0,
                "message": (
                    f"{len(available_files)} fixture files found,"
                    f" {len(missing)} tools missing fixtures"
                    if missing
                    else f"All {len(required_tools)} tool fixtures present"
                ),
                "required_tools": len(required_tools),
                "available_fixtures": len(available_files),
                "missing": list(missing),
            }
            if missing:
                all_valid = False
        except Exception as e:
            results["fixtures"] = {"valid": False, "message": str(e)}
            all_valid = False

    # No validation targets provided — show usage hint
    if not results:
        click.echo(
            "Nothing to validate."
            " Provide at least one of: --pack, --agent, --baseline, --check-fixtures",
        )
        raise SystemExit(1)

    # Render results and exit with appropriate code
    formatter = OutputFormatter(output_format)
    formatter.format_validation(results)

    if not all_valid:
        raise SystemExit(1)
