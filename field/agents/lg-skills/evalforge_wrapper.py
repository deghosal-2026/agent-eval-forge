"""EvalForge field-test wrapper for the langgraph-skills-agent repo.

The repo's graphs/ tree uses absolute imports (`from skills_agent.config import`)
and relies on LangGraph CLI putting `graphs/` on sys.path. This shim adds that
path and re-exports the compiled graph so the EvalForge langgraph adapter can
import it in-process.
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

_GRAPHS = _REPO / "graphs"
if str(_GRAPHS) not in sys.path:
    sys.path.insert(0, str(_GRAPHS))

from skills_agent.agent import graph  # noqa: E402
