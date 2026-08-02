"""Caching layer for evaluation runs and schema validation.

Provides in-memory and file-backed caches to avoid redundant computation:

- :class:`RunCache`: In-memory cache for run artifacts keyed by pack hash.
- :class:`JudgeCache`: File-backed cache for LLM judge results with TTL.
- :class:`SchemaCache`: Thread-safe in-memory cache for pack schema validation.
"""

import logging

from evalforge.cache.judge_cache import JudgeCache
from evalforge.cache.run_cache import RunCache
from evalforge.cache.schema_cache import SchemaCache

logger = logging.getLogger("evalforge.cache")

__all__ = ["JudgeCache", "RunCache", "SchemaCache"]
