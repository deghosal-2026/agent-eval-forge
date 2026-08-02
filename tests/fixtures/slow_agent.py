"""Mock agent that sleeps for timeout testing of IsolatedAdapter."""
import time
from types import SimpleNamespace


def build_agent(payload):
    time.sleep(30)
    return SimpleNamespace(invoke=lambda state, config=None: {"messages": []})
