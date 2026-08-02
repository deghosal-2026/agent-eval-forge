"""External benchmark integration: SWE-bench, WebArena, and custom formats.

Provides :class:`BenchmarkLoader` for parsing external benchmark datasets and
converting them to EvalForge scenario packs, and :class:`BenchmarkRegistry`
for plugging in custom benchmark formats at runtime.
"""

from evalforge.benchmarks.loader import BenchmarkLoader, BenchmarkRegistry, BenchmarkTask

__all__ = ["BenchmarkLoader", "BenchmarkRegistry", "BenchmarkTask"]
