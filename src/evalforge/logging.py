"""Logging configuration for EvalForge library consumers.

Usage:
    import logging
    logging.getLogger("evalforge").setLevel(logging.INFO)

EvalForge modules log via ``logging.getLogger("evalforge.<module>")``.

Logger hierarchy::
    evalforge               - root package logger (WARNING by default)
    evalforge.scoring       - scoring engine operations
    evalforge.cache         - cache hits, misses, corruptions
    evalforge.security      - sandbox, audit, policy enforcement
    evalforge.runner        - scenario runner lifecycle
    evalforge.loading       - pack YAML/JSON loading and validation
"""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.WARNING) -> None:
    """Configure the evalforge logger with a basic handler if none exists."""
    logger = logging.getLogger("evalforge")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(handler)
    logger.setLevel(level)
