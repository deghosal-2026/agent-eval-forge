"""EvalForge — a framework-agnostic evaluation harness for tool-using AI agents.

Package root. Intentionally minimal: no heavy imports at top level so that
`import evalforge` stays cheap and any import-time errors surface in the
specific submodule that caused them rather than masking everything.

Version is read from a single source of truth here and consumed by:
  - the CLI `version` command (src/evalforge/cli/__main__.py)
  - pyproject.toml is NOT sourced from here — hatchling reads the static
    `[project] version`. Keep both in sync on release (see M9/M10).
"""

__version__ = "0.1.0"
