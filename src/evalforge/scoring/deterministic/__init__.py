"""Deterministic scorers — rule-based evaluation without LLM judge calls.

This sub-package contains all purely deterministic scorers that evaluate
agent behavior using string matching, set operations, and arithmetic checks.
These are fast, cheap, and fully reproducible — no LLM calls involved.

Modules:
    args    — Tool-argument correctness (exact and subset matching).
    budget  — Step efficiency and cost-budget adherence.
    gates   — Deterministic gates for hybrid metrics (policy adherence, retry discipline).
    grounding — Factual consistency, source citation, output grounding, contradiction detection.
    output  — Schema validity and field presence checks.
    phantom — Phantom-step detection for trajectory efficiency.
    tools   — Tool-call correctness, required tool presence, disallowed-tool avoidance.
"""

from evalforge.scoring.deterministic import phantom  # noqa: F401
