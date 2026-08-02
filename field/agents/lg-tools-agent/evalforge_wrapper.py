"""EvalForge field-test wrapper for oap-langgraph-tools-agent repo.

The repo's graph function is async (designed for LangGraph CLI). This shim
calls it synchronously via asyncio.run and re-exports the compiled graph.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_VENV = _REPO / ".venv"
if _VENV.exists():
    _VENV_LIB = _VENV / "lib"
    _PYTHON_DIRS = sorted(_VENV_LIB.glob("python*/site-packages"))
    for _d in _PYTHON_DIRS:
        if str(_d) not in sys.path:
            sys.path.insert(0, str(_d))

import tools_agent.agent as _ta
from langchain_core.runnables import RunnableConfig


def _build():
    config = RunnableConfig()
    return asyncio.run(_ta.graph(config))


graph = _build()