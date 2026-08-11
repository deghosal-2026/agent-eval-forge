r"""``evalforge run`` — run a scenario pack against an agent and score the results.

This is the primary entry point for end-to-end evaluation. It orchestrates
the full pipeline:

1. **Parse** the scenario pack YAML/JSON into ``ScenarioPack`` models.
2. **Invoke** each scenario against the agent via the configured adapter.
3. **Capture** normalized ``RunArtifact``\ s to ``.evalforge/runs/<run_id>/``.
4. **Score** each artifact against the scenario's expected behavior using
   deterministic scorers and an optional LLM-as-judge.
5. **Compare** (optional) against a saved golden baseline and produce a delta
   report.
6. **Report** in JSON (default), Markdown, or terminal (Rich) format.

All imports from the core library are deferred to function scope so that
``evalforge --help`` and ``evalforge run --help`` stay fast and never trigger
optional-dependency failures (e.g., missing ``rich`` or LLM SDKs).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

from evalforge.cli.util import parse_agent_spec
from evalforge.models.manifest import collect_host_info
from evalforge.scoring.judge.client import JudgeClient


def _execution_environment() -> dict[str, str]:
    return collect_host_info()


def _resolve_judge(judge_spec: str | None) -> JudgeClient | None:
    """Parse a judge spec like ``openai:gpt-4o-mini`` into a ``JudgeClient``.

    Supported providers:

    ========= ============= ============================================
    Provider  Default model Environment variable
    ========= ============= ============================================
    openai    gpt-4o-mini   ``OPENAI_API_KEY`` (required)
    anthropic claude-3-haiku ``ANTHROPIC_API_KEY`` (required)
    ollama    llama3        (local — no key needed)
    mlx       Qwen3.5-9B   (Apple Silicon — no key needed)
    mock      —             Returns ``MockJudge(score=1.0)``
    ========= ============= ============================================

    Args:
        judge_spec: The judge spec string (e.g. ``"openai:gpt-4o-mini"``,
            ``"mock"``, or ``None`` to skip LLM judging).

    Returns:
        A configured ``JudgeClient`` instance, or ``None`` if no judge is
        requested.

    Raises:
        click.UsageError: If a required API key is not set.
        click.BadParameter: If the provider is unknown.
    """
    if judge_spec is None:
        return None

    import os

    # Split on first colon: "openai:gpt-4o-mini" => provider="openai", model="gpt-4o-mini"
    parts = judge_spec.split(":", 1)
    provider = parts[0]
    model = parts[1] if len(parts) > 1 else None

    if provider == "openai":
        from evalforge.scoring.judge.openai import OpenAIClient

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise click.UsageError(
                "OPENAI_API_KEY environment variable not set "
                "(needed for openai judge)"
            )
        return OpenAIClient(api_key=api_key, model=model or "gpt-4o-mini")

    elif provider == "anthropic":
        from evalforge.scoring.judge.anthropic import AnthropicClient

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise click.UsageError(
                "ANTHROPIC_API_KEY environment variable not set "
                "(needed for anthropic judge)"
            )
        return AnthropicClient(api_key=api_key, model=model or "claude-3-haiku-20240307")

    elif provider == "ollama":
        from evalforge.scoring.judge.ollama import OllamaClient

        return OllamaClient(model=model or "llama3")

    elif provider == "mlx":
        from evalforge.scoring.judge.mlx import MLXJudgeClient

        return MLXJudgeClient(model=model or "mlx-community/Llama-3.2-3B-Instruct-4bit")

    elif provider == "mock":
        from evalforge.scoring.judge.mock import MockJudge

        return MockJudge(score=1.0)

    else:
        raise click.BadParameter(f"unknown judge provider: {provider}")


@click.command()
@click.option(
    "--pack",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the scenario pack YAML/JSON file",
)
@click.option(
    "--agent",
    required=True,
    help="Agent spec (e.g. 'python:my_module.run' or './my_agent' for subprocess)",
)
@click.option(
    "--agent-function",
    default=None,
    help="Override function name for Python-import adapters (default: 'run')",
)
@click.option("--baseline", default=None, help="Optional baseline name for regression comparison")
@click.option("--judge", default=None, help="Judge spec (e.g. 'openai:gpt-4o-mini' or 'mock')")
@click.option(
    "--output", default=".evalforge", show_default=True,
    help="Output directory for runs and artifacts",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "markdown", "terminal", "html", "github-actions"]),
    default="json",
    show_default=True,
    help="Output format for the run report",
)
@click.option("--tags", default=None, help="Comma-separated tag filter (e.g. 'retrieval,safety')")
@click.option(
    "--workers",
    default=1,
    type=int,
    show_default=True,
    help="Number of parallel workers (1 = serial execution)",
)
@click.option(
    "--timeout",
    default=120,
    type=int,
    show_default=True,
    help="Per-scenario timeout in seconds",
)
@click.option("--ci", is_flag=True, help="CI mode: JSON-only output, structured exit codes")
@click.option(
    "--quiet", is_flag=True,
    help="Suppress stdout output (useful in CI when writing files)",
)
@click.option(
    "--fixtures",
    is_flag=True,
    default=None,
    help="Run with fixtures (deterministic mode, no live tool calls)",
)
@click.option(
    "--live",
    is_flag=True,
    default=None,
    help="Run with live tool calls (disable fixtures)",
)
@click.option(
    "--fixtures-dir",
    default="scenarios/fixtures",
    show_default=True,
    help="Directory containing fixture JSON files",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable judge result caching",
)
@click.option(
    "--sandbox",
    is_flag=True,
    help="Run in sandbox mode (restricted env, no API key passthrough)",
)
@click.option(
    "--max-outstanding",
    default=None,
    type=int,
    help="Maximum outstanding parallel tasks (backpressure). Default: no limit.",
)
@click.option(
    "--compare-mode",
    type=click.Choice(["rescore", "snapshot"]),
    default="rescore",
    help="Baseline comparison mode: rescore (default, re-evaluate) or snapshot (use stored scores)",
)
@click.option(
    "--trust",
    type=click.Choice(["builtin", "local", "external"]),
    default=None,
    help="Override pack trust level",
)
@click.option(
    "--seed",
    default=None,
    type=int,
    help="Set a deterministic seed for reproducible evaluation runs",
)
@click.option(
    "--model",
    default=None,
    help="Explicitly declare the agent model name (e.g. 'gpt-4o', 'claude-3-opus'). "
    "Overrides model detection from the agent config.",
)
@click.option(
    "--explain-policy",
    is_flag=True,
    help="Explain why the current adapter/trust combo is or isn't allowed",
)
@click.option(
    "--telemetry",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help="Export metrics to the given JSON file path",
)
@click.option(
    "--no-manifest",
    is_flag=True,
    help="Skip emitting run-manifest.json (saves ~100ms, useful in CI)",
)
@click.option(
    "--fail-on",
    type=click.Choice(["compatibility", "safety", "quality", "all"]),
    default=None,
    help="Fail (non-zero exit) if the given score dimension drops below threshold (0.8)",
)
@click.option(
    "--fail-on-divergence",
    type=click.Choice(["critical", "warning", "all"]),
    default=None,
    help="Exit non-zero when divergences between deterministic and LLM judge exist",
)
def run(
    pack: str,
    agent: str,
    agent_function: str | None,
    baseline: str | None,
    judge: str | None,
    output: str,
    output_format: str,
    tags: str | None,
    workers: int,
    timeout: int,
    ci: bool,
    quiet: bool,
    fixtures: bool | None,
    fixtures_dir: str,
    no_cache: bool,
    sandbox: bool,
    trust: str | None,
    live: bool | None,
    max_outstanding: int | None = None,
    compare_mode: str = "rescore",
    explain_policy: bool = False,
container_runtime: str | None = None,
    no_manifest: bool = False,
    seed: int | None = None,
    model: str | None = None,
    telemetry: str | None = None,
    fail_on: str | None = None,
    fail_on_divergence: str | None = None,
) -> None:
    """Run a scenario pack against an agent, score results, and optionally compare.

    This is the primary EvalForge workflow: load scenarios, invoke the agent,
    score the results, and produce a report. If ``--baseline`` is provided the
    candidate run is compared against the golden baseline for regression detection.

    Args:
        pack: Path to the scenario pack file.
        agent: Agent spec string (adapter:value).
        baseline: Optional baseline name for regression comparison.
        judge: Judge spec for LLM-as-judge scoring.
        output: Base output directory.
        output_format: Output format (json, markdown, terminal, html).
        tags: Comma-separated tag filter.
        workers: Number of parallel workers.
        timeout: Per-scenario timeout in seconds.
        ci: CI mode flag (forces JSON output).
        quiet: Suppress stdout.
        fixtures: Enable deterministic fixtures.
        fixtures_dir: Fixture files directory.
        no_cache: Disable judge caching.
        sandbox: Run in sandbox mode.
        trust: Override pack trust level.
        live: Disable fixtures (run live).
        max_outstanding: Backpressure limit for parallel tasks.
        compare_mode: Baseline comparison mode (rescore or snapshot).
        explain_policy: Print trust policy evaluation then exit.
        seed: Deterministic seed for reproducibility.
        telemetry: Path to export telemetry JSON.

    Exits with:
        0 on success, 1 if any scenario failed or policy is denied.
    """
    # Core library imports deferred so --help is fast and optional dependencies
    # (rich, openai, anthropic) are only loaded when actually used.
    from evalforge.cli.formatter import OutputFormatter
    from evalforge.runner import Runner, generate_run_id
    from evalforge.scoring.engine import ScoringEngine

    # CI mode forces JSON output (machine-readable, no prompts)
    if ci:
        output_format = "json"

    if seed is not None:
        # Set a deterministic seed so runs are reproducible
        from evalforge.determinism import SeedManager

        _seed_manager = SeedManager(seed=seed)
        _seed_manager.set_global_seed()

    if fixtures is not None and live is not None:
        raise click.UsageError("--fixtures and --live are mutually exclusive")

    # Parse the agent spec and extend with CLI-level overrides
    agent_config = parse_agent_spec(agent)
    agent_config["timeout_seconds"] = timeout
    if agent_function:
        agent_config["function"] = agent_function
    if fixtures is not None:
        agent_config["fixtures"] = fixtures
    if live is not None:
        agent_config["fixtures"] = not live
    agent_config["fixtures_dir"] = fixtures_dir
    agent_config["sandbox"] = sandbox
    agent_config["container_runtime"] = container_runtime
    if model:
        # Explicitly declare the model so it is recorded in the run artifacts'
        # agent metadata and surfaced in baseline comparison (see #255).
        agent_config["model"] = model

    # Parse the optional tag filter
    tag_list = tags.split(",") if tags else None

    # Step 1: Load pack and create runner
    runner = Runner(agent_config=agent_config, output_dir=output)
    runner.load_pack(pack)

    if trust:
        runner.pack.pack.trust = trust

    # Enforce trust policy before running
    from evalforge.security.policy import TrustLevel, TrustPolicy
    pack_trust: TrustLevel = runner.pack.pack.trust  # type: ignore[assignment]
    agent_type = agent_config.get("type", "subprocess")
    sandbox_mode = bool(agent_config.get("sandbox", False))
    policy = TrustPolicy(trust=pack_trust, adapter_type=agent_type, sandbox=sandbox_mode)
    allowed, reason = policy.allowed()
    if explain_policy:
        click.echo(
            f"Policy evaluation for trust={pack_trust}, "
            f"adapter={agent_type}, sandbox={sandbox_mode}:"
        )
        click.echo(f"  {'ALLOWED' if allowed else 'DENIED'}: {reason or 'no restrictions'}")
        raise SystemExit(0 if allowed else 1)
    if not allowed:
        raise click.UsageError(reason or "adapter/trust combination not allowed")

    # Step 2: Generate run ID and begin audit trail
    run_id = generate_run_id()
    from evalforge.security.audit import AuditTrail
    from evalforge.security.sanitize import sanitize_config

    audit = AuditTrail(base_dir=output)
    audit.record("run_start", {
        "run_id": run_id,
        "pack": pack,
        "agent": sanitize_config(agent_config),
        "sandbox": bool(agent_config.get("sandbox", False)),
        "ci": ci,
    })

    if agent_config.get("sandbox", False):
        from evalforge.security.sandbox import SANDBOX_ALLOWLIST
        audit.record("sandbox_active", {"sandbox_allowlist": sorted(SANDBOX_ALLOWLIST)})

    # Step 3: Run all scenarios (or a filtered subset) and capture artifacts
    import time

    start_ms = int(time.time() * 1000)
    artifacts = runner.run_all(
        tags=tag_list, run_id=run_id, workers=workers, max_outstanding=max_outstanding,
        emit_manifest=not no_manifest,
    )
    duration_ms = int(time.time() * 1000) - start_ms

    # Step 3: Score artifacts against scenario expectations
    from evalforge.cache import JudgeCache as _JudgeCache

    judge_cache = None if no_cache else _JudgeCache(base_dir=output)
    engine = ScoringEngine(runner.pack, judge_cache=judge_cache)
    judge_client = _resolve_judge(judge)
    run_score = engine.score_run(artifacts, judge=judge_client)

    # Step 4: Build the result payload for output and persistence
    pack_meta = runner.pack.pack
    result = {
        "schema_version": "v0.1",
        "run_id": run_id,
        "pack_name": pack_meta.name,
        "pack_version": pack_meta.version,
        "execution_environment": _execution_environment(),
        "total_scenarios": (
            run_score.totals["passed"]
            + run_score.totals["warned"]
            + run_score.totals["failed"]
        ),
        "passed": run_score.totals["passed"],
        "warned": run_score.totals["warned"],
        "failed": run_score.totals["failed"],
        "exit_code": run_score.exit_code,
        "duration_ms": duration_ms,
        "safety_violations": run_score.safety_violations,
        "dimensions": run_score.dimensions,
        "scenario_scores": {
            sid: {
                "status": ss.status,
                "safety_violations": ss.safety_violations,
                "metrics": {
                    m: {
                        "score": sr.score,
                        "threshold": sr.threshold,
                        "passed": sr.passed,
                        "category": sr.category,
                        "source": sr.source,
                        "error": sr.error,
                    }
                    for m, sr in ss.metric_results.items()
                },
            }
            for sid, ss in run_score.scenario_scores.items()
        },
    }

    result["cache_stats"] = engine.cache_stats if not no_cache else {}

    # Build scoring_breakdown: deterministic, llm_judge, and divergences
    scoring_det: list[dict[str, Any]] = []
    scoring_judge: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []

    for sid, ss in run_score.scenario_scores.items():
        det_has_pass = False
        det_has_fail = False
        judge_has_pass = False
        judge_has_fail = False
        for mname, mr in ss.metric_results.items():
            entry: dict[str, Any] = {
                "metric": mname,
                "score": mr.score,
                "threshold": mr.threshold,
                "passed": mr.passed,
                "scenario_id": sid,
            }
            if mr.source == "deterministic":
                scoring_det.append(entry)
                if mr.passed is True:
                    det_has_pass = True
                elif mr.passed is False:
                    det_has_fail = True
            elif mr.source == "judge":
                entry["rationale"] = mr.detail.get("rationale", "")
                scoring_judge.append(entry)
                if mr.passed is True:
                    judge_has_pass = True
                elif mr.passed is False:
                    judge_has_fail = True

        # Classify per-scenario divergences
        if det_has_fail and judge_has_pass:
            divergences.append({
                "scenario_id": sid,
                "type": "critical",
                "detail": "Deterministic check(s) failed but LLM judge passed",
            })
        if det_has_pass and judge_has_fail:
            divergences.append({
                "scenario_id": sid,
                "type": "warning",
                "detail": "Deterministic check(s) passed but LLM judge failed",
            })

    result["scoring_breakdown"] = {
        "deterministic": scoring_det,
        "llm_judge": scoring_judge,
        "divergences": divergences,
    }

    # Step 5 (optional): Compare against a saved baseline
    if baseline:
        from evalforge.baselines.store import BaselineStore
        from evalforge.comparison.engine import ComparisonEngine
        from evalforge.comparison.report import ComparisonReport

        store = BaselineStore(base_dir=f"{output}/baselines")
        try:
            baseline_obj = store.load(baseline)

            if compare_mode == "snapshot":
                # Snapshot mode: reconstruct RunScore from stored score data
                # rather than re-running the LLM judge.
                if baseline_obj.score_snapshot:
                    from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult

                    scenario_scores: dict[str, ScenarioScore] = {}
                    for sid, sd in baseline_obj.score_snapshot.get("scenario_scores", {}).items():
                        metric_results: dict[str, ScoreResult] = {}
                        for mn, mr in sd.get("metrics", {}).items():
                            metric_results[mn] = ScoreResult(
                                metric=mn,
                                score=mr.get("score"),
                                threshold=mr.get("threshold"),
                                passed=mr.get("passed"),
                                category=mr.get("category", "correctness"),
                                blocking=mr.get("blocking", False),
                                detail=mr.get("detail", {}),
                                source=mr.get("source", "deterministic"),
                                error=mr.get("error"),
                            )
                        scenario_scores[sid] = ScenarioScore(
                            scenario_id=sid,
                            metric_results=metric_results,
                            status=sd.get("status", "failed"),
                            safety_violations=sd.get("safety_violations", []),
                        )
                    baseline_score = RunScore(
                        scenario_scores=scenario_scores,
                        totals=baseline_obj.score_snapshot.get(
                            "totals", {"passed": 0, "warned": 0, "failed": 0}
                        ),
                        safety_violations=baseline_obj.score_snapshot.get("safety_violations", []),
                        exit_code=baseline_obj.score_snapshot.get("exit_code", 1),
                    )
                else:
                    # Fallback: rescore when no snapshot exists
                    click.echo("Baseline has no snapshot, falling back to rescoring", err=True)
                    baseline_score = engine.score_run(baseline_obj.runs, judge=judge_client)
            else:
                # Rescore mode: re-run the judge on the baseline artifacts
                baseline_score = engine.score_run(baseline_obj.runs, judge=judge_client)

            comp_engine = ComparisonEngine(runner.pack)
            comp_result = comp_engine.compare(
                baseline_score=baseline_score,
                candidate_score=run_score,
                baseline=baseline_obj,
            )
            report = ComparisonReport(
                baseline_name=baseline,
                candidate_name=run_id,
                result=comp_result,
                candidate_score=run_score,
            )
            formatter = OutputFormatter(output_format)
            formatter.format_comparison(
                report, output_path=f"{output}/runs/{run_id}/comparison.md",
            )
            result["comparison"] = report.to_json() if output_format == "json" else {}
        except FileNotFoundError:
            click.echo(
                f"Warning: baseline '{baseline}' not found, skipping comparison",
                err=True,
            )

    # Step 6: Output
    formatter = OutputFormatter(output_format, quiet=quiet)
    output_content = formatter.format_run_result(result)
    if output_content:
        report_ext = "html" if output_format == "html" else "md"
        report_path = Path(f"{output}/runs/{run_id}/report.{report_ext}")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output_content)

    # Persist scores as JSON for later comparison and analysis
    with open(Path(f"{output}/runs/{run_id}/scores.json"), "w") as f:
        json.dump(result, f, indent=2)

    # Write to GITHUB_STEP_SUMMARY in CI mode
    if output_format == "github-actions":
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write(output_content or "")

    # Step 6a: Record audit trail completion
    audit.record("run_complete", {
        "run_id": run_id,
        "exit_code": run_score.exit_code,
        "passed": run_score.totals["passed"],
        "failed": run_score.totals["failed"],
        "safety_violations": run_score.safety_violations,
    })

    # Step 6b: Export telemetry if requested
    if telemetry:
        metrics = runner.metrics
        telemetry_data = {
            "run_id": run_id,
            "metrics": {
                "total_scenarios": metrics.total_scenarios,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "warnings": metrics.warnings,
                "total_duration_ms": metrics.total_duration_ms,
                "avg_scenario_duration_ms": metrics.avg_scenario_duration_ms,
                "avg_agent_cost_usd": metrics.avg_agent_cost_usd,
                "avg_judge_cost_usd": metrics.avg_judge_cost_usd,
                "cache_hit_rate": metrics.cache_hit_rate,
                "safety_violations": metrics.safety_violations,
                "agents_per_second": metrics.agents_per_second,
            },
            "cache_stats": engine.cache_stats if not no_cache else {},
        }
        Path(telemetry).parent.mkdir(parents=True, exist_ok=True)
        Path(telemetry).write_text(json.dumps(telemetry_data, indent=2))

    # Summary to stdout
    if not quiet:
        env = _execution_environment()
        click.echo(f"Run complete: {run_id}")
        click.echo(
            f"  Passed: {run_score.totals['passed']},"
            f" Warned: {run_score.totals['warned']},"
            f" Failed: {run_score.totals['failed']}"
        )
        if run_score.dimensions:
            dims = run_score.dimensions
            click.echo(
                f"  Dimensions: compatibility={dims.get('compatibility', 'N/A'):.2f},"
                f" safety={dims.get('safety', 'N/A'):.2f},"
                f" quality={dims.get('quality', 'N/A'):.2f}"
            )
        click.echo(f"  Exit code: {run_score.exit_code}")
        click.echo(f"  Environment: {env['os']} / {env['arch']} / Python {env['python']}")
        if run_score.safety_violations:
            click.echo(
                f"  Safety violations: {', '.join(run_score.safety_violations)}"
            )
        det_passed = sum(1 for d in scoring_det if d.get("passed") is True)
        det_total = len(scoring_det)
        judge_passed = sum(1 for d in scoring_judge if d.get("passed") is True)
        judge_total = len(scoring_judge)
        crit_divs = sum(1 for d in divergences if d["type"] == "critical")
        warn_divs = sum(1 for d in divergences if d["type"] == "warning")
        click.echo(
            f"  Score: {run_score.exit_code} |"
            f" Deterministic: {det_passed}/{det_total} |"
            f" LLM Judge: {judge_passed}/{judge_total} |"
            f" Divergences: {crit_divs} critical, {warn_divs} warning"
        )

    # --fail-on gating: non-zero exit if a dimension is below threshold (0.8)
    _FAIL_THRESHOLD = 0.8
    if fail_on:
        dims = run_score.dimensions
        targets = ["compatibility", "safety", "quality"] if fail_on == "all" else [fail_on]
        for dim in targets:
            if dim in dims and dims[dim] < _FAIL_THRESHOLD:
                click.echo(
                    f"Dimension '{dim}' score {dims[dim]:.2f} below threshold {_FAIL_THRESHOLD}",
                    err=True,
                )
                raise SystemExit(1)

    # --fail-on-divergence gating: non-zero exit when divergences exist
    if fail_on_divergence:
        divs = divergences
        if fail_on_divergence == "critical":
            critical_divs = [d for d in divs if d["type"] == "critical"]
            if critical_divs:
                click.echo(
                    f"Critical divergences detected: {len(critical_divs)}",
                    err=True,
                )
                raise SystemExit(5)
        elif fail_on_divergence == "warning":
            warning_divs = [d for d in divs if d["type"] == "warning"]
            if warning_divs:
                click.echo(
                    f"Warning divergences detected: {len(warning_divs)}",
                    err=True,
                )
                raise SystemExit(5)
        elif fail_on_divergence == "all" and divs:
            click.echo(
                f"Divergences detected: {len(divs)}",
                err=True,
            )
            raise SystemExit(5)

    raise SystemExit(run_score.exit_code)
