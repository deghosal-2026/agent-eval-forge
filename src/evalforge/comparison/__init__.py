"""Comparison engine: candidate-vs-baseline deltas and reports.

Compares a candidate run against a golden baseline at three levels —
per scenario, per family/tag, and aggregate pack level (spec §"Comparison
Model"). Detects new failures, new passes, regressions, and improvements,
and emits JSON + markdown reports with CI-friendly exit codes (0 pass, 4 =
safety violation).

M3 implements the `ComparisonEngine` and `ComparisonReport`.
"""
