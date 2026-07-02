from __future__ import annotations
from typing import Dict, Callable, Any
import traceback

TOOLS: Dict[str, Callable[..., Any]] = {}


def tool(name: str):
    """Decorator to register a tool."""
    def deco(fn):
        TOOLS[name] = fn
        return fn

    return deco


import inspect

def list_tools() -> str:
    """List available tools with signatures and docstrings."""
    lines = []
    for name, fn in sorted(TOOLS.items()):
        sig = inspect.signature(fn)
        doc = inspect.getdoc(fn) or "No description."
        # Compact docstring: first line only
        doc = doc.split("\n")[0]
        lines.append(f"{name}{sig} - {doc}")
    return "\n".join(lines)


def dispatch(name: str, **kwargs) -> Any:
    """Dispatch a tool call with error handling."""
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}
    
    try:
        return TOOLS[name](**kwargs)
    except Exception as e:
        return {
            "error": f"Tool execution failed: {str(e)}",
            "traceback": traceback.format_exc()
        }
