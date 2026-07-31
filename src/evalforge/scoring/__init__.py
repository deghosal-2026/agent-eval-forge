"""Scoring engine: deterministic scorers, LLM-as-judge scorers, and hybrid scoring.

Scoring is what makes EvalForge a *release gate* rather than a logger: every
metric returns a score (0.0-1.0), a threshold, and a pass/fail verdict
(spec §"Scoring Engine").

Evaluation hierarchy is safety > correctness > efficiency — safety violations
hard-fail regardless of other scores. Deterministic scorers are cheap and
reproducible (exact match, schema validity, tool-called, ...); LLM-as-judge
scorers are used only when configured and semantically needed. Hybrid scoring
chains them: deterministic gate first, judge fallback only when required.

M2 implements these. This package init keeps the registry import light.
"""
