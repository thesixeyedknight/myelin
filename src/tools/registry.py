from __future__ import annotations
from typing import Dict, Callable, Any

TOOLS: Dict[str, Callable[..., Any]] = {}


def tool(name: str):
    def deco(fn):
        TOOLS[name] = fn
        return fn

    return deco


def list_tools() -> str:
    return ", ".join(sorted(TOOLS.keys()))


def dispatch(name: str, **kwargs):
    if name not in TOOLS:
        raise KeyError(f"Unknown tool: {name}")
    return TOOLS[name](**kwargs)
