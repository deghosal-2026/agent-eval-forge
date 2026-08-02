"""EvalForge field-test wrapper for langgraph-mcp-agent-template repo.

The repo uses src/ layout; this shim adds src/ to sys.path and re-exports
the compiled graph so the EvalForge langgraph adapter can import it.
"""

from __future__ import annotations

import site
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent
_VENV = _REPO / ".venv"
if _VENV.exists():
    _VENV_LIB = _VENV / "lib"
    _PYTHON_DIRS = sorted(_VENV_LIB.glob("python*/site-packages"))
    for _d in _PYTHON_DIRS:
        if str(_d) not in sys.path:
            sys.path.insert(0, str(_d))

_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mcp_agent import graph  # noqa: E402