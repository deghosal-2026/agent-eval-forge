"""Comparison report — JSON and Markdown report generation (spec §"Report Generation").

Produces two output formats from a ComparisonResult:
- JSON: Machine-readable, CI-friendly, suitable for automated processing.
- Markdown: Human-readable, designed for PR comments and CI summary output.

Both formats include:
- Summary statistics (total, regressed, improved, new failures/passes)
- Per-scenario deltas with status classification
- Per-family/tag deltas
- Cost deltas (USD)
- Safety violation reporting
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evalforge.comparison.engine import ComparisonResult
from evalforge.scoring.result import RunScore


@dataclass
class ComparisonReport:
    """Formats a comparison result as JSON or Markdown.

    Attributes:
        baseline_name: Human-readable name of the baseline (e.g. "v1.0.0").
        candidate_name: Human-readable name of the candidate (e.g. "PR-42").
        result: The ComparisonResult containing all delta data.
        candidate_score: The RunScore from the candidate run, used for
            exit code and safety violation reporting.
    """

    baseline_name: str
    candidate_name: str
    result: ComparisonResult
    candidate_score: RunScore

    def to_json(self) -> dict[str, Any]:
        """Generate a JSON-serializable dict of the comparison report.

        The output structure matches the spec's §"Comparison Model" schema:
        - baseline_name, candidate_name: identifiers for the two sides
        - aggregate: top-level summary with totals, deltas, and exit code
        - scenario_deltas: per-scenario breakdown
        - family_deltas: per-family/tag breakdown
        """
        return {
            "baseline_name": self.baseline_name,
            "candidate_name": self.candidate_name,
            "aggregate": {
                "total_scenarios": self.result.aggregate["total_scenarios"],
                "regressed": self.result.aggregate["regressed"],
                "improved": self.result.aggregate["improved"],
                "new_failures": self.result.aggregate["new_failures"],
                "new_passes": self.result.aggregate["new_passes"],
                "unchanged": self.result.aggregate["unchanged"],
                "overall_score_delta": self.result.aggregate["overall_score_delta"],
                "candidate_totals": self.candidate_score.totals,
                "candidate_exit_code": self.candidate_score.exit_code,
                "safety_violations": self.candidate_score.safety_violations,
                "cost_delta_usd": self.result.aggregate.get("cost_delta_usd", 0),
            },
            "scenario_deltas": self.result.scenario_deltas,
            "family_deltas": self.result.family_deltas,
        }

    def to_markdown(self) -> str:
        """Generate a human-readable Markdown report.

        The report includes:
        1. Header with baseline → candidate identity
        2. Summary table with aggregate statistics
        3. Per-scenario delta table with regression/improvement labels
        4. Per-family delta table (if any families exist)
        5. Safety violations highlighted (if any)
        6. Cost delta in USD

        Designed to be posted as a CI summary comment or PR comment.
        """
        lines: list[str] = []
        lines.append(f"# Comparison Report: {self.baseline_name} \u2192 {self.candidate_name}")
        lines.append("")

        agg = self.result.aggregate
        lines.append("## Summary")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Total Scenarios | {agg['total_scenarios']} |")
        lines.append(f"| Regressed | {agg['regressed']} |")
        lines.append(f"| Improved | {agg['improved']} |")
        lines.append(f"| New Failures | {agg['new_failures']} |")
        lines.append(f"| New Passes | {agg['new_passes']} |")
        lines.append(f"| Unchanged | {agg['unchanged']} |")
        lines.append(f"| Overall Score Delta | {agg['overall_score_delta']:+.3f} |")
        lines.append(f"| Cost Delta (USD) | {agg.get('cost_delta_usd', 0):+.6f} |")
        lines.append(f"| Exit Code | {self.candidate_score.exit_code} |")
        if self.candidate_score.safety_violations:
            lines.append(
                f"| Safety Violations | {', '.join(self.candidate_score.safety_violations)} |"
            )
        lines.append("")

        lines.append("## Per-Scenario Deltas")
        lines.append("| Scenario | Baseline | Candidate | Delta | Status |")
        lines.append("|---|---|---|---|---|")
        for sid, delta in sorted(self.result.scenario_deltas.items()):
            label: str
            if delta["regressed"]:
                label = "regressed"
            elif delta["improved"]:
                label = "improved"
            else:
                label = "unchanged"
            delta_str = (
                f"{delta['delta']:+.3f}" if delta["delta"] is not None else "-"
            )
            lines.append(
                f"| {sid} | {delta['baseline_score'] or '-'} | "
                f"{delta['candidate_score'] or '-'} | {delta_str} | {label} |"
            )
        lines.append("")

        if self.result.family_deltas:
            lines.append("## Per-Family Deltas")
            lines.append("| Family | Baseline Avg | Candidate Avg | Delta |")
            lines.append("|---|---|---|---|")
            for fam, fd in sorted(self.result.family_deltas.items()):
                lines.append(
                    f"| {fam} | {fd['baseline_avg']:.3f} | {fd['candidate_avg']:.3f} | "
                    f"{fd['score_delta']:+.3f} |"
                )
            lines.append("")

        lines.append("---")
        return "\n".join(lines)
