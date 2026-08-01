"""Output formatting for CLI commands.

Provides a shared ``OutputFormatter`` class that renders results as JSON,
Markdown, terminal (Rich table), or GitHub Actions summary output across
all CLI commands. JSON is the default and is CI-friendly; Markdown is
designed for PR/commit comments; terminal uses Rich for colored display;
``github-actions`` generates output compatible with ``$GITHUB_STEP_SUMMARY``.

All ``rich`` imports are deferred to class- or method-scope to keep
``evalforge --help`` fast when terminal output is not requested.
"""

from __future__ import annotations

import json
from typing import Any

from evalforge.comparison.report import ComparisonReport


class OutputFormatter:
    """Format CLI output in JSON, Markdown, terminal, or GitHub Actions mode.

    Args:
        format: One of ``"json"``, ``"markdown"``, ``"terminal"``, or
            ``"github-actions"``. Defaults to ``"json"``.
    """

    def __init__(self, format: str = "json", quiet: bool = False) -> None:
        self.format = format
        self.quiet = quiet

    def format_run_result(self, result: dict[str, Any]) -> str | None:
        """Format a run result payload.

        Args:
            result: The run result dictionary from ``run.py``.

        Returns:
            A formatted string for Markdown/terminal/GitHub Actions, or
            ``None`` for JSON (printed directly to stdout).
        """
        if self.format == "json":
            if not self.quiet:
                print(json.dumps(result, indent=2))
            return None
        elif self.format == "github-actions":
            return self._run_result_github_actions(result)
        elif self.format == "markdown":
            return self._run_result_markdown(result)
        else:
            return self._run_result_terminal(result)

    def format_comparison(
        self, report: ComparisonReport, output_path: str | None = None
    ) -> str | None:
        """Format a comparison report.

        Args:
            report: The ``ComparisonReport`` to format.
            output_path: Optional file path to write the output to.

        Returns:
            A formatted string for Markdown/terminal/GitHub Actions, or
            ``None`` for JSON (printed directly).
        """
        if self.format == "json":
            output = json.dumps(report.to_json(), indent=2)
            if output_path:
                with open(output_path, "w") as f:
                    f.write(output)
            print(output)
            return None
        elif self.format == "markdown":
            md = report.to_markdown()
            if output_path:
                with open(output_path, "w") as f:
                    f.write(md)
            return md
        elif self.format == "github-actions":
            return self._comparison_github_actions(report)
        else:
            return self._comparison_terminal(report)

    def format_validation(self, results: dict[str, Any]) -> str | None:
        """Format validation results.

        Args:
            results: Validation target results dict.

        Returns:
            A formatted string for Markdown/terminal/GitHub Actions, or
            ``None`` for JSON.
        """
        if self.format == "json":
            print(json.dumps(results, indent=2))
            return None
        elif self.format == "github-actions":
            return self._validation_github_actions(results)
        elif self.format == "markdown":
            return self._validation_markdown(results)
        else:
            return self._validation_terminal(results)

    def format_test_result(self, summary: dict[str, Any]) -> str | None:
        """Format a multi-pack test run result.

        Args:
            summary: The aggregated test run summary dict.

        Returns:
            A formatted string or ``None`` for JSON.
        """
        if self.format == "json":
            print(json.dumps(summary, indent=2))
            return None
        elif self.format == "github-actions":
            return self._test_result_github_actions(summary)
        elif self.format == "markdown":
            return self._test_result_markdown(summary)
        else:
            return self._test_result_terminal(summary)

    def _run_result_markdown(self, result: dict[str, Any]) -> str:
        """Build a Markdown run report table."""
        lines = [
            f"# Run Result: {result['run_id']}",
            "",
            "## Summary",
            "| Metric | Value |",
            "|---|---|",
            f"| Pack | {result.get('pack_name', 'unknown')} |",
            f"| Scenarios | {result.get('total_scenarios', 0)} |",
            f"| Passed | {result.get('passed', 0)} |",
            f"| Warned | {result.get('warned', 0)} |",
            f"| Failed | {result.get('failed', 0)} |",
            f"| Duration | {result.get('duration_ms', 0)}ms |",
            f"| Exit Code | {result.get('exit_code', 0)} |",
        ]
        if result.get("safety_violations"):
            lines.append(
                f"| Safety Violations |"
                f" {', '.join(result['safety_violations'])} |"
            )
        lines.extend(["", "---"])
        return "\n".join(lines)

    def _run_result_github_actions(self, result: dict[str, Any]) -> str:
        """Build a GitHub Actions summary from a run result."""
        lines = [
            "## EvalForge Run Results",
            "",
            f"**Run:** `{result['run_id']}`  \n"
            f"**Pack:** {result.get('pack_name', 'unknown')} v{result.get('pack_version', '?')}  \n"
            f"**Duration:** {result.get('duration_ms', 0)}ms  \n"
            f"**Exit Code:** {result.get('exit_code', 0)}",
            "",
            "| Status | Count |",
            "|---|---|",
            f"| ✅ Passed | {result.get('passed', 0)} |",
            f"| ⚠️ Warned | {result.get('warned', 0)} |",
            f"| ❌ Failed | {result.get('failed', 0)} |",
        ]
        if result.get("safety_violations"):
            lines.append(
                f"| 🛑 Safety Violations |"
                f" {', '.join(result['safety_violations'])} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _run_result_terminal(self, result: dict[str, Any]) -> str:
        """Build a terminal (Rich) run report table."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title=f"Run: {result['run_id']}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Pack", result.get("pack_name", "unknown"))
        table.add_row("Scenarios", str(result.get("total_scenarios", 0)))
        table.add_row("Passed", str(result.get("passed", 0)))
        table.add_row("Warned", str(result.get("warned", 0)))
        table.add_row("Failed", str(result.get("failed", 0)))
        table.add_row("Duration", f"{result.get('duration_ms', 0)}ms")
        table.add_row("Exit Code", str(result.get("exit_code", 0)))
        if result.get("safety_violations"):
            table.add_row("Safety", ", ".join(result["safety_violations"]))
        console.print(table)
        return ""

    def _comparison_github_actions(self, report: ComparisonReport) -> str:
        """Build a GitHub Actions summary from a comparison report."""
        agg = report.result.aggregate
        lines = [
            "## EvalForge Comparison Report",
            "",
            f"**Baseline:** `{report.baseline_name}` \u2192"
            f" **Candidate:** `{report.candidate_name}`  \n",
            "| Metric | Value |",
            "|---|---|",
            f"| Total Scenarios | {agg['total_scenarios']} |",
            f"| Regressed | {agg['regressed']} |",
            f"| Improved | {agg['improved']} |",
            f"| New Failures | {agg['new_failures']} |",
            f"| New Passes | {agg['new_passes']} |",
            f"| Unchanged | {agg['unchanged']} |",
            f"| Score Delta | {agg['overall_score_delta']:+.3f} |",
        ]
        if report.candidate_score.safety_violations:
            lines.append(
                "| 🛑 Safety Violations |"
                f" {', '.join(report.candidate_score.safety_violations)} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _comparison_terminal(self, report: ComparisonReport) -> str:
        """Build a terminal (Rich) comparison report table."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        agg = report.result.aggregate
        console.print(
            f"[bold]Comparison: {report.baseline_name}"
            f" \u2192 {report.candidate_name}[/bold]"
        )
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Total Scenarios", str(agg["total_scenarios"]))
        table.add_row("Regressed", f"[red]{agg['regressed']}[/red]")
        table.add_row("Improved", f"[green]{agg['improved']}[/green]")
        table.add_row("New Failures", f"[red]{agg['new_failures']}[/red]")
        table.add_row("New Passes", f"[green]{agg['new_passes']}[/green]")
        table.add_row("Unchanged", str(agg["unchanged"]))
        table.add_row("Score Delta", f"{agg['overall_score_delta']:+.3f}")
        if report.candidate_score.safety_violations:
            table.add_row(
                "Safety",
                f"[red]{', '.join(report.candidate_score.safety_violations)}[/red]",
            )
        console.print(table)
        return ""

    def _validation_github_actions(self, results: dict[str, Any]) -> str:
        """Build a GitHub Actions summary from validation results."""
        lines = ["## EvalForge Validation Results", ""]
        all_valid = all(r.get("valid") for r in results.values())
        if all_valid:
            lines.append("✅ All validations passed\n")
        for key, value in results.items():
            status = "✅" if value.get("valid") else "❌"
            lines.append(f"**{key}:** {status} — {value.get('message', '')}  ")
        lines.append("")
        return "\n".join(lines)

    def _validation_markdown(self, results: dict[str, Any]) -> str:
        """Build a Markdown validation report."""
        lines = ["# Validation Results", ""]
        for key, value in results.items():
            status = "✅" if value.get("valid") else "❌"
            lines.append(f"## {key} {status}")
            for k, v in value.items():
                if k != "valid":
                    lines.append(f"- **{k}:** {v}")
            lines.append("")
        lines.append("---")
        return "\n".join(lines)

    def _validation_terminal(self, results: dict[str, Any]) -> str:
        """Build a terminal (Rich) validation report."""
        from rich.console import Console

        console = Console()
        all_valid = all(r.get("valid") for r in results.values())
        if all_valid:
            console.print("[green]\u2713 All validations passed[/green]")
        for key, value in results.items():
            status = (
                "[green]\u2713[/green]"
                if value.get("valid")
                else "[red]\u2717[/red]"
            )
            console.print(f"{status} {key}: {value.get('message', '')}")
        return ""

    def _test_result_github_actions(self, summary: dict[str, Any]) -> str:
        """Build a GitHub Actions summary from a multi-pack test run."""
        lines = [
            "## EvalForge Test Run Results",
            "",
            f"**Packs:** {summary.get('packs', 0)}  \n"
            f"**Scenarios:** {summary.get('total_scenarios', 0)}  \n"
            f"**Duration:** {summary.get('duration_ms', 0)}ms",
            "",
            "| Status | Count |",
            "|---|---|",
            f"| ✅ Passed | {summary.get('passed', 0)} |",
            f"| ⚠️ Warned | {summary.get('warned', 0)} |",
            f"| ❌ Failed | {summary.get('failed', 0)} |",
        ]
        if summary.get("safety_violations"):
            lines.append(
                "| 🛑 Safety Violations |"
                f" {', '.join(summary['safety_violations'])} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _test_result_markdown(self, summary: dict[str, Any]) -> str:
        """Build a Markdown multi-pack test run report."""
        lines = [
            "# EvalForge Test Run Results",
            "",
            "## Aggregate Summary",
            "| Metric | Value |",
            "|---|---|",
            f"| Packs | {summary.get('packs', 0)} |",
            f"| Total Scenarios | {summary.get('total_scenarios', 0)} |",
            f"| Passed | {summary.get('passed', 0)} |",
            f"| Warned | {summary.get('warned', 0)} |",
            f"| Failed | {summary.get('failed', 0)} |",
            f"| Duration | {summary.get('duration_ms', 0)}ms |",
        ]
        if summary.get("safety_violations"):
            lines.append(
                "| Safety Violations |"
                f" {', '.join(summary['safety_violations'])} |"
            )
        lines.extend(["", "## Per-Pack Results", ""])
        for r in summary.get("results", []):
            pack = r.get("pack_name", r.get("pack_path", "unknown"))
            if "error" in r:
                lines.append(f"- **{pack}**: ❌ {r['error']}")
            else:
                lines.append(
                    f"- **{pack}**: ✅ {r.get('passed', 0)} passed,"
                    f" ⚠️ {r.get('warned', 0)} warned,"
                    f" ❌ {r.get('failed', 0)} failed"
                )
        lines.append("")
        return "\n".join(lines)

    def _test_result_terminal(self, summary: dict[str, Any]) -> str:
        """Build a terminal (Rich) multi-pack test run report."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        console.print("[bold]EvalForge Test Run Results[/bold]")
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Packs", str(summary.get("packs", 0)))
        table.add_row("Scenarios", str(summary.get("total_scenarios", 0)))
        table.add_row("Passed", str(summary.get("passed", 0)))
        table.add_row("Warned", str(summary.get("warned", 0)))
        table.add_row("Failed", str(summary.get("failed", 0)))
        table.add_row("Duration", f"{summary.get('duration_ms', 0)}ms")
        if summary.get("safety_violations"):
            table.add_row(
                "Safety", ", ".join(summary["safety_violations"])
            )
        console.print(table)

        for r in summary.get("results", []):
            pack = r.get("pack_name", r.get("pack_path", "unknown"))
            if "error" in r:
                console.print(f"  [red]✗[/red] {pack}: {r['error']}")
            else:
                console.print(
                    f"  [green]✓[/green] {pack}:"
                    f" {r.get('passed', 0)}p/{r.get('warned', 0)}w/{r.get('failed', 0)}f"
                )
        return ""
